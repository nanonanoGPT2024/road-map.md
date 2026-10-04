# Kurikulum Rekayasa Perangkat Lunak iOS Enterprise
## Bab 10: CI/CD, Automasi Fastlane, dan App Store Deployment
### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   Mendesain dan mengimplementasikan arsitektur CI/CD iOS skala enterprise yang aman, terisolasi, dan *reproducible* menggunakan Fastlane, Fastlane Match, dan GitHub Actions / GitLab CI.
*   Menguasai mekanisme internal *code signing* Apple (Certificates, Private Keys, Provisioning Profiles) dan mengelolanya secara terpusat tanpa konflik antar-tim via *Fastlane Match* dengan backend storage terenkripsi (Git/S3/GCS).
*   Mengonfigurasi autentikasi App Store Connect API berbasis JSON Web Token (JWT / `.p8`) untuk memotong ketergantungan pada otentikasi interaktif 2FA (Two-Factor Authentication).
*   Mengoptimalkan waktu eksekusi *pipeline* (*build times*) melalui strategi caching komprehensif (DerivedData, SPM, CocoaPods artifacts) dan paralelisasi pengujian (*test sharding*).
*   Mengotomatisasi siklus rilis produksi: *binary compilation*, integrasi dSYM (Crashlytics/Sentry), *metadata management*, *TestFlight phased distribution*, hingga *App Store Phased Rollout*.

---

### 2. Prerequisite
*   Pemahaman mendalam tentang ekosistem kompilasi iOS: `clang`, `swiftc`, `xcodebuild`, dan struktur berkas `.ipa` / `.xcarchive`.
*   Akses administratif atau Developer Role pada Apple Developer Enterprise / Organization Program.
*   Kemahiran menengah dalam scripting Ruby (sintaks dasar, Gemfile, Bundler) dan shell scripting (Bash/Zsh).
*   Pengalaman praktis mengoperasikan CI Runner (GitHub Actions runner, GitLab Runner, atau MacStadium bare-metal instance).

---

### 3. Concept & Internal Architecture (Mendalam)

#### 3.1. Anatomi Apple Code Signing
Code signing pada iOS adalah sistem proteksi kriptografis multi-lapis yang menjamin integritas biner dan identitas penerbit sebelum kernel sistem operasi (XNU) mengeksekusi instruksi:

```
[Apple Worldwide Developer Relations CA (WWDR)]
                     │
      ┌──────────────┴──────────────┐
      ▼                             ▼
[Development Certificate]     [Distribution Certificate]
(RSA 2048 / ECC Private Key)  (RSA 2048 / ECC Private Key)
      │                             │
      └──────────────┬──────────────┘
                     ▼
           [Provisioning Profile] (.mobileprovision)
           ├── Entitlements (aps-environment, keychain-access-groups, etc.)
           ├── Whitelisted Device UDIDs (Ad-Hoc / Development only)
           ├── Team ID & App ID (Bundle Identifier prefix)
           └── Embedded Public Certificate (Matches Distribution/Dev Cert)
                     │
                     ▼ Validated by Kernel
      [Mach-O Binary Code Directory Signature] (Embedded in LC_CODE_SIGNATURE)
```

1. **Certificates & Asymmetric Keys**: Terdiri atas pasangan Private Key (disimpan secara lokal di macOS Keychain atau HSM CI) dan Public Certificate yang ditandatangani oleh Apple WWDR Root CA. Private Key digunakan untuk membubuhkan tanda tangan kriptografis pada blok *Code Directory Hash* dari biner Mach-O.
2. **Entitlements**: Berkas XML property list (`.plist`) yang menetapkan kapabilitas sandbox aplikasi (misalnya Push Notifications, App Groups, Sign In with Apple).
3. **Provisioning Profile (`.mobileprovision`)**: Berkas bertanda tangan CMS (Cryptographic Message Syntax) dari Apple yang mengikat sertifikat, Entitlements, Bundle ID, dan daftar UDID perangkat yang diizinkan (pada profil non-App Store).
4. **Validasi Runtime**: Saat aplikasi diluncurkan, *amfid* (*Apple Mobile File Integrity Daemon*) memvalidasi bahwa signature biner cocok dengan sertifikat di dalam provisioning profile, dan profile tersebut telah diverifikasi oleh Apple Root CA.

#### 3.2. Fastlane Execution Model & Action Pipeline
Fastlane dibangun di atas runtime Ruby. Inti dari Fastlane adalah `FastlaneCore` dan *Action Engine*:

```
                        CLI Call: fastlane release
                                  │
                                  ▼
                            [Fastfile]
                                  │
                      (Lane Execution Context)
                                  │
      ┌───────────────────────────┼───────────────────────────┐
      ▼                           ▼                           ▼
[fastlane_require]        [Action Runner]             [State Machine]
Plugins/Gems resolution   Validation & Dynamic        Context Engine (SharedValues)
                          Action Dispatch             LANE_NAME, IPA_OUTPUT_PATH, etc.
                                  │
                                  ▼
               [Shell Wrapper / Subprocess Invocation]
                   ├── security (macOS Keychain)
                   ├── xcodebuild / xcrun
                   └── altool / iTMSTransporter
```

*   **Action Runner**: Setiap instruksi di dalam `lane` (seperti `match`, `gym`, `pilot`) merupakan subclass dari `Fastlane::Action`. Action memiliki definisi parameter formal, dependensi platform, dan nilai balik yang diteruskan ke `Actions.lane_context`.
*   **Context Passing**: Variabel lingkungan global dan *lane context* (seperti `Actions.lane_context[SharedValues::IPA_OUTPUT_PATH]`) menghubungkan hasil eksekusi antar *tool*. Misalnya, output biner dari `gym` (`build_app`) secara otomatis dibaca oleh `pilot` (`upload_to_testflight`) tanpa konfigurasi path manual.

#### 3.3. Fastlane Match: Arsitektur Single Source of Truth
Fastlane Match mengimplementasikan filosofi *GitOps* untuk sertifikat dan provisioning profiles:

```
  Developer Workstation                     CI/CD Headless Runner
┌─────────────────────────┐               ┌─────────────────────────┐
│ fastlane match dev      │               │ fastlane match appstore │
└────────────┬────────────┘               └────────────┬────────────┘
             │                                         │
             │ (Git Protocol over SSH / HTTPS)         │
             ▼                                         ▼
   ┌────────────────────────────────────────────────────────┐
   │ Encrypted Storage Repository (GitHub / GitLab / S3)    │
   │ ├── certs/                                             │
   │ │   ├── distribution/ (Encrypted with OpenSSL / AES256)│
   │ │   └── development/                                   │
   │ └── profiles/                                          │
   │     ├── distribution/ (*.mobileprovision)              │
   │     └── appstore/                                      │
   └────────────────────────────────────────────────────────┘
                               │
               (Decrypt via MATCH_PASSWORD)
                               ▼
        ┌──────────────────────────────────────────────┐
        │ Ephemeral Keychain (fastlane_tmp_keychain)   │
        │ - Dibuat dinamis per build                   │
        │ - Menghindari polusi System/Login Keychain   │
        │ - Di-destroy otomatis pasca build            │
        └──────────────────────────────────────────────┘
```

Pendekatan ini memecahkan masalah klasik "*Code signing identity not found*" dan "*Revoked certificate crisis*" di lingkungan enterprise yang melibatkan puluhan insinyur:
1. Tidak ada anggota tim yang membuat sertifikat secara mandiri di Apple Developer Portal.
2. Sertifikat dan kunci privat dienkripsi menggunakan AES-256 via OpenSSL (`MATCH_PASSWORD`).
3. Pada lingkungan CI headless, Match menginstansiasi *ephemeral keychain* sementara, mengimpor sertifikat ke dalamnya, membuka akses partisi keychain untuk `codesign`, dan menghapusnya saat pipeline selesai (*teardown*).

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Xcode GUI) | Pendekatan Modern Enterprise (Fastlane + CI/CD) |
| :--- | :--- | :--- |
| **Code Signing** | Manual export `.p12` antar developer, sertifikat sering ter-*revoke* secara tidak sengaja. | Terpusat via `match`. Tersimpan terenkripsi di Git/S3. Otomatis dan deterministik. |
| **Otentikasi Apple** | Akun Apple ID pribadi dengan 2FA SMS/Push, rentan terblokir sesi. | App Store Connect API Key (`.p8`) berbasis JWT. *Stateless*, aman, dan didesain untuk mesin. |
| **Build Artifact** | Xcode Organizer export manual. Parameter build rentan human-error. | `gym` (`build_app`) membungkus `xcodebuild` dengan arsitektur compiler flags yang terkontrol ketat. |
| **Distribusi** | Drag-and-drop file via Transporter App atau Xcode GUI upload. | Distribusi instan via `pilot` (TestFlight) dan `deliver` (Production) langsung dari artefak biner. |
| **Auditability** | Tidak terlacak, dependensi build berada di workstation masing-masing insinyur. | *Infrastructure as Code* (IaC). Setiap commit, rilis, dan tagging terlacak di git log. |

---

### 5. How (Workflow Detail)

Alur kerja rilis enterprise terbagi ke dalam empat fase utama:

```
[Phase 1: CI Bootstrap]
  ├── Clone repository (Git)
  ├── Set up ruby environment via Gemfile.lock (Bundler)
  ├── Cache restoration (SPM dependencies, Gem cache, DerivedData)
  └── Create temporary isolated Keychain

[Phase 2: Signing & Provisioning (Fastlane Match)]
  ├── Authenticate to App Store Connect via JWT (.p8 API Key)
  ├── Download encrypted certs/profiles from backend storage
  ├── Decrypt payload with MATCH_PASSWORD
  └── Install identity & profiles into temporary Keychain

[Phase 3: Compilation & Packaging (Gym / build_app)]
  ├── Set build/version numbers programmatically
  ├── Execute xcodebuild archive with specified configuration
  ├── Export .xcarchive to .ipa using automated exportOptions.plist
  └── Extract and archive dSYM symbol files

[Phase 4: Distribution & Telemetry Upload]
  ├── Upload .ipa to App Store Connect (TestFlight / App Store)
  ├── Upload dSYMs to Sentry / Firebase Crashlytics
  ├── Post notification to Slack / Teams channels
  └── Destroy temporary Keychain & Clean Workspace
```

---

### 6. Analogy & Diagram ASCII

Bayangkan proses pengiriman paket fisik berharga internasional:
*   **Biner Mach-O**: Dokumen berharga yang harus dikirim.
*   **Developer Certificate**: Stempel segel lilin unik milik perusahaan.
*   **Provisioning Profile**: Manifest bea cukai yang menetapkan siapa penerimanya, rute yang boleh dilewati, dan barang bawaan khusus yang diizinkan.
*   **Fastlane Match**: Brankas pusat berpengaman kombinasi rahasia (`MATCH_PASSWORD`) yang menyimpan stempel resmi perusahaan; staf bea cukai manapun (CI Runner) dapat menggunakannya jika memiliki kunci kombinasi yang sah.
*   **App Store Connect API Key (`.p8`)**: Paspor diplomatik yang memberikan akses langsung melewati gerbang pemeriksaan tanpa perlu otentikasi biometrik/SMS manual di setiap langkah.

```
       WORKSTATION                         CI PIPELINE RUNNER
┌─────────────────────────┐             ┌─────────────────────────┐
│     Software Engineer   │             │   GitHub Actions Agent  │
│  git push origin main   │             │  (Headless macOS Host)  │
└────────────┬────────────┘             └────────────┬────────────┘
             │                                       │
             ▼                                       ▼
     [ Remote Git Repo ] ────────(Webhook)───▶ [ Load Fastfile ]
                                                     │
                                                     ▼
                                           [ match (Read-Only) ]
                                                     │
                                                     ▼
                                           [ Create Keychain ]
                                                     │
                                                     ▼
                                           [ gym (Build IPA) ]
                                                     │
                                                     ▼
                                           [ pilot (TestFlight) ]
                                                     │
                                                     ▼
                                          [ Clean up Keychain ]
```

---

### 7. Simple Example & Practical Example

#### 7.1. Struktur Berkas CI/CD iOS Enterprise
```
.
├── .github/
│   └── workflows/
│       └── release_pipeline.yml
├── fastlane/
│   ├── Appfile
│   ├── Fastfile
│   ├── Matchfile
│   └── Pluginfile
├── Gemfile
├── Gemfile.lock
└── AppEnterprise.xcodeproj (atau .xcworkspace)
```

#### 7.2. `Gemfile` (Menjaga determinisme versi runtime)
```ruby
source "https://rubygems.org"

gem "fastlane", "2.222.0"
gem "cocoapods", "1.15.2"
gem "xcpretty", "0.4.0"
```

#### 7.3. `fastlane/Appfile`
```ruby
app_identifier("com.enterprise.app")
apple_id("dev-ops@enterprise.com")
team_id("ABC1234XYZ")
itc_team_id("987654321")
```

#### 7.4. `fastlane/Matchfile`
```ruby
git_url("git@github.com:enterprise-org/ios-certificates-repo.git")
storage_mode("git")
type("appstore")
app_identifier(["com.enterprise.app", "com.enterprise.app.NotificationService"])
username("dev-ops@enterprise.com")
team_id("ABC1234XYZ")
shallow_clone(true)
clone_branch_headless(true)
```

#### 7.5. `fastlane/Fastfile` (Standar Industri Enterprise)
```ruby
default_platform(:ios)

platform :ios do
  before_all do
    # Memastikan ekosistem Ruby selaras dengan Gemfile.lock
    ensure_bundle_exec
    
    # Inisialisasi App Store Connect API Key menggunakan file .p8
    app_store_connect_api_key(
      key_id: ENV["APP_STORE_CONNECT_KEY_ID"],
      issuer_id: ENV["APP_STORE_CONNECT_ISSUER_ID"],
      key_content: ENV["APP_STORE_CONNECT_KEY_CONTENT"],
      is_key_content_base64: true,
      in_house: false
    )
  end

  desc "Lane untuk CI: Menjalankan static analysis, unit testing, dan code coverage"
  lane :test do
    run_tests(
      workspace: "AppEnterprise.xcworkspace",
      devices: ["iPhone 15 Pro"],
      scheme: "AppEnterprise",
      clean: true,
      code_coverage: true,
      output_directory: "./fastlane/test_output",
      output_types: "html,junit"
    )
  end

  desc "Lane untuk CI/CD: Distribusi Internal TestFlight"
  lane :beta do |options|
    keychain_name = "ephemeral_ci_keychain"
    keychain_password = SecureRandom.hex(16)

    # 1. Isolasi Keychain untuk eksekusi headless
    create_keychain(
      name: keychain_name,
      password: keychain_password,
      default_keychain: true,
      unlock: true,
      timeout: 3600,
      lock_when_sleeps: false
    )

    # 2. Mengambil Certificate & Profile via Match dalam mode Read-Only
    match(
      type: "appstore",
      readonly: is_ci,
      keychain_name: keychain_name,
      keychain_password: keychain_password
    )

    # 3. Sinkronisasi Build Number berbasis Run Number CI
    build_number = options[:build_number] || Time.now.strftime("%Y%m%d%H%M")
    increment_build_number(
      build_number: build_number,
      xcodeproj: "AppEnterprise.xcodeproj"
    )

    # 4. Kompilasi dan Packaging Binary (.ipa)
    build_app(
      workspace: "AppEnterprise.xcworkspace",
      scheme: "AppEnterprise-Release",
      configuration: "Release",
      output_directory: "./build/artifacts",
      output_name: "AppEnterprise.ipa",
      clean: true,
      export_method: "app-store",
      export_options: {
        signingStyle: "manual",
        compileBitcode: false,
        provisioningProfiles: {
          "com.enterprise.app" => "match AppStore com.enterprise.app",
          "com.enterprise.app.NotificationService" => "match AppStore com.enterprise.app.NotificationService"
        }
      }
    )

    # 5. Upload Symbol Crashlytics/Sentry (Opsional jika SDK digunakan)
    # upload_symbols_to_crashlytics(gsp_path: "./AppEnterprise/GoogleService-Info.plist")

    # 6. Upload biner ke Apple TestFlight
    upload_to_testflight(
      ipa: "./build/artifacts/AppEnterprise.ipa",
      skip_waiting_for_build_processing: true,
      distribute_external: false,
      notify_external_testers: false
    )

    # 7. Teardown Keamanan: Hapus Ephemeral Keychain
    delete_keychain(name: keychain_name) if File.exist?(File.expand_path("~/Library/Keychains/#{keychain_name}-db"))
  end

  after_all do |lane|
    UI.success("Lane #{lane} berhasil dieksekusi tanpa anomali.")
  end

  error do |lane, exception|
    # Pastikan keychain dibersihkan jika terjadi kegagalan sistematis
    keychain_name = "ephemeral_ci_keychain"
    delete_keychain(name: keychain_name) if File.exist?(File.expand_path("~/Library/Keychains/#{keychain_name}-db"))
    UI.error("Error pada lane #{lane}: #{exception.message}")
  end
end
```

#### 7.6. `.github/workflows/release_pipeline.yml`
```yaml
name: iOS Enterprise Deployment Pipeline

on:
  push:
    branches:
      - main

concurrency:
  group: ios-deploy-${{ github.ref }}
  cancel-in-progress: true

jobs:
  build_and_deploy:
    name: Build, Sign, and Deploy to TestFlight
    runs-on: macos-14 # Apple Silicon (M1/M2 Runner)
    timeout-minutes: 60

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 1

      - name: Select Xcode Version
        run: sudo xcode-select -s /Applications/Xcode_15.4.app/Contents/Developer

      - name: Setup Ruby and Bundler Dependencies
        uses: ruby/setup-ruby@v1
        with:
          ruby-version: '3.2'
          bundler-cache: true

      - name: Cache Swift Package Manager (SPM)
        uses: actions/cache@v4
        with:
          path: .build
          key: ${{ runner.os }}-spm-${{ hashFiles('**/Package.resolved') }}
          restore-keys: |
            ${{ runner.os }}-spm-

      - name: Setup SSH Agent for Match Git Repository
        uses: webfactory/ssh-agent@v0.9.0
        with:
          ssh-private-key: ${{ secrets.MATCH_GIT_PRIVATE_SSH_KEY }}

      - name: Execute Fastlane Beta Lane
        env:
          APP_STORE_CONNECT_KEY_ID: ${{ secrets.ASC_KEY_ID }}
          APP_STORE_CONNECT_ISSUER_ID: ${{ secrets.ASC_ISSUER_ID }}
          APP_STORE_CONNECT_KEY_CONTENT: ${{ secrets.ASC_KEY_CONTENT_BASE64 }}
          MATCH_PASSWORD: ${{ secrets.FASTLANE_MATCH_PASSWORD }}
        run: |
          bundle exec fastlane ios beta build_number:${{ github.run_number }}

      - name: Upload Build Artifacts (IPA & dSYM)
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: app-release-artifacts
          path: |
            build/artifacts/*.ipa
            build/artifacts/*.dSYM.zip
          retention-days: 14
```

---

### 8. Real World Case Study (Enterprise Scale)

#### Konteks: SuperApp FinTech dengan Arsitektur Multi-Target & Whitelabel
Sebuah institusi perbankan regional memelihara 1 biner inti yang dikompilasi menjadi 4 varian aplikasi *whitelabel* (Bank Retail, Bank Syariah, Private Banking, dan Corporate Wealth) dengan 3 App Extensions (WidgetKit, Push Notification Service Extension, dan Share Extension) per varian. Total terdapat 16 Bundle Identifier unik.

#### Tantangan Skalabilitas & Operasional
1. **Certificate Limit Exhaustion**: Batas sertifikat distribusi Apple Developer (maksimal 3 per akun Enterprise/Organization) sering habis karena developer secara manual menekan tombol *"Automatically manage signing"* pada Xcode masing-masing.
2. **Pipeline Duration Overload**: Satu siklus build lengkap untuk 4 varian memakan waktu **2 jam 45 menit** pada Mac mini bare-metal server.
3. **Flaky Build Environments**: CI gagal secara acak karena dialog pop-up macOS (*"codesign wants to access key '...' in your keychain"*).

#### Solusi Arsitektural Terintegrasi
1. **Sentralisasi Identitas dengan Fastlane Match & Shared Wildcard/Multi-ID**:
   * Menstandarisasi sertifikat tunggal untuk semua target via `Matchfile` yang mengelola 16 provisioning profile secara atomik.
   * Parameter `readonly: true` diterapkan secara ketat di CI untuk mencegah pembuatan identitas baru di portal Apple.
2. **Pemanfaatan Ephemeral Headless Keychain**:
   * Fastlane menginjeksi `security set-key-partition-list` langsung ke keychain sementara CI runner sehingga macOS security daemon tidak memunculkan prompt otentikasi GUI interaktif.
3. **Matrix Builds & Cache Topology**:
   * Melakukan refactoring CI menggunakan GitHub Actions Matrix strategy. Keempat varian dikompilasi secara paralel di atas 4 macOS Apple Silicon runner independen.
   * DerivedData dan ccache diisolasi per target menggunakan network hashing key berbasis lockfile dependensi.

#### Hasil Terukur (Metrics & Performance Gain)
* Waktu total deployment untuk seluruh ekosistem varian berkurang dari **165 menit** menjadi **22 menit** (penurunan ~86%).
* Insiden *failed build* yang diakibatkan oleh *Code Signing Identity Mismatch* turun menjadi **0%** dalam kurun waktu 12 bulan audit produksi.
* Tidak ada lagi interupsi interaktif 2FA berkat adopsi menyeluruh App Store Connect API Key (`.p8`).

---

### 9. Trade-offs

| Aspek | Pilihan A: Self-Hosted Bare Metal (Mac mini / Mac Studio) | Pilihan B: Cloud-Hosted Runners (GitHub Mac Silicon / Bitrise) |
| :--- | :--- | :--- |
| **Biaya Operasional (Cost)** | CapEx tinggi di awal (pengadaan perangkat fisik), namun OpEx per build sangat murah untuk volume build tinggi. | Zero CapEx. Model penagihan Pay-per-minute (OpEx tinggi jika pipeline berjalan ratusan jam per bulan). |
| **Kecepatan & Performa** | Sangat tinggi; isolasi memori lokal, latensi disk rendah, caching DerivedData persisten lintas build. | Variabel; latensi download image OS, caching harus diunduh/diunggah melalui jaringan per *job*. |
| **Isolasi & Keamanan** | Berisiko terjadi polusi state (stateful). Sisa build sebelumnya dapat mencemari build saat ini jika disk teardown gagal. | Terisolasi secara mutlak (ephemeral VM). Setiap job dimulai dari *clean-state image*. |
| **Beban Pemeliharaan** | Tim DevOps wajib menangani macOS patching, Xcode update, MDM provisioning, dan hardware uptime. | Zero maintenance infrastruktur OS. Xcode versi baru langsung disediakan oleh vendor via image tag. |

| Aspek | Pilihan A: Fastlane Match Git Backend | Pilihan B: Fastlane Match Cloud Storage (AWS S3 / Google Cloud) |
| :--- | :--- | :--- |
| **Manajemen Akses** | Menggunakan SSH Deploy Keys. Kontrol akses granular berbasis repo GitHub/GitLab. | Menggunakan AWS IAM Roles / OpenID Connect (OIDC). Sangat aman tanpa hardcoded credentials. |
| **Auditability** | Sangat transparan; riwayat sertifikat dapat ditelusuri melalui `git log` dan commit signature. | Audit trail bergantung pada AWS CloudTrail / S3 Object Access Logs; tidak ada riwayat commit biner visual. |

---

### 10. Common Mistakes & Troubleshooting

#### 10.1. Error: `User interaction is not allowed (-25308)`
*   **Akar Masalah**: Tool `codesign` mencoba mengakses private key di macOS Keychain, tetapi keychain dalam status terkunci (*locked*) atau System Integrity Protection menghalangi akses non-interaktif karena private key tidak mengizinkan akses biner `codesign`.
*   **Solusi**:
    Gunakan action `unlock_keychain` dan tetapkan partisi akses secara eksplisit sebelum kompilasi dimulai:
    ```bash
    security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH"
    ```
    Atau dalam Fastlane:
    ```ruby
    unlock_keychain(
      path: keychain_path,
      password: keychain_password,
      add_to_search_list: true
    )
    ```

#### 10.2. Error: `App Store Connect API: 403 Forbidden - Not Authorized`
*   **Akar Masalah**: Kredensial `.p8` memiliki konfigurasi role yang tidak memadai pada App Store Connect (misalnya role hanya "Developer", padahal butuh hak "Admin" atau "App Manager" untuk upload metadata/binary), atau waktu mesin CI mengalami clock drift (JWT Apple menolak deviasi waktu > 5 menit).
*   **Solusi**:
    1. Pastikan API Key di App Store Connect memiliki minimal role **App Manager** atau **Admin**.
    2. Jalankan sinkronisasi NTP pada host runner:
       ```bash
       sudo sntp -sS time.apple.com
       ```

#### 10.3. Error: `Provisioning profile doesn't include signing certificate`
*   **Akar Masalah**: Sertifikat yang tersimpan di dalam Provisioning Profile yang aktif telah di-revoke atau expired, sementara sertifikat di keychain dibuat ulang tanpa men-generate ulang profile-nya.
*   **Solusi**:
    Jalankan Fastlane Match dengan flag `force_for_new_devices: true` atau eksekusi `nuke`:
    ```bash
    bundle exec fastlane match appstore --force
    ```
    *(Gunakan `fastlane match nuke` hanya jika Anda yakin ingin mematikan semua sertifikat lama secara global).*

---

### 11. Best Practices (Production Checklist)

#### Pre-build Validation
- [ ] Semua dependensi dikunci menggunakan versi deterministik (`Gemfile.lock`, `Podfile.lock`, `Package.resolved`).
- [ ] Versi Xcode didefinisikan secara tegas melalui berkas `.xcode-version` dan dieksekusi via `xcode-select`.
- [ ] Ephemeral Keychain dibuat dinamis dan ditandai sebagai default search list selama job berlangsung.

#### Secrets & Security Guardrails
- [ ] Kunci privat App Store Connect (`.p8`) disimpan dalam CI Secret Manager sebagai string Base64 yang dienkripsi; tidak pernah disimpan di disk sebagai plain text.
- [ ] Berkas `Matchfile` menggunakan Git backend yang privat dengan restricted access dan audit logging aktif.
- [ ] Password dekripsi Match (`MATCH_PASSWORD`) memiliki entropi tinggi (> 32 karakter alfanumerik acak).

#### Build & Compilation Efficiency
- [ ] Flag `clean: false` digunakan secara hati-hati pada caching DerivedData; pastikan invalidasi cache dilakukan setiap kali `Package.resolved` atau `Podfile.lock` berubah.
- [ ] Kompilasi dSYM selalu diaktifkan (`DEBUG_INFORMATION_FORMAT = dwarf-with-dsym`) pada konfigurasi rilis untuk memungkinkan crash symbolication pasca-rilis.
- [ ] Hindari kompilasi arsitektur ganda yang redundan; targetkan hanya `arm64` untuk hardware produksi modern.

#### Post-Build & Cleanup
- [ ] Seluruh artefak sensitif, keychain sementara, dan token otentikasi dimusnahkan (*teardown*) pada blok `ensure` atau `after_all` / `error`.
- [ ] Simpan dSYM dan `.ipa` pada build pipeline artifact storage dengan retention policy terukur (misal: 14 hari).
- [ ] Rilis TestFlight didistribusikan ke kelompok QA internal terlebih dahulu sebelum masuk ke track publik/eksternal.

---

### 12. Hands-on Practice

Buat struktur direktori untuk mengimplementasikan infrastruktur CI/CD berbasis Fastlane ini:

```bash
mkdir -p hands-on/m02/fastlane
mkdir -p hands-on/m02/.github/workflows
cd hands-on/m02
```

#### Langkah 1: Inisialisasi Gemfile
Buat file `hands-on/m02/Gemfile`:
```ruby
source "https://rubygems.org"

gem "fastlane", "~> 2.222.0"
```
Jalankan di terminal:
```bash
bundle config set --local path 'vendor/bundle'
bundle install
```

#### Langkah 2: Konfigurasi Appfile dan Matchfile
Buat file `hands-on/m02/fastlane/Appfile`:
```ruby
app_identifier("com.enterprise.production")
apple_id("ci-agent@enterprise.com")
team_id("TEAMID1234")
```

Buat file `hands-on/m02/fastlane/Matchfile`:
```ruby
git_url("https://github.com/enterprise-org/mock-certificates.git")
storage_mode("git")
type("appstore")
app_identifier(["com.enterprise.production"])
shallow_clone(true)
```

#### Langkah 3: Implementasi Fastfile Produksi
Buat file `hands-on/m02/fastlane/Fastfile`:
```ruby
default_platform(:ios)

platform :ios do
  lane :build_production do
    keychain_name = "ci_temp_keychain"
    keychain_pass = "temporary_password_123"

    create_keychain(
      name: keychain_name,
      password: keychain_pass,
      default_keychain: true,
      unlock: true,
      timeout: 1800,
      lock_when_sleeps: false
    )

    UI.message("Keychain sementara berhasil dikonfigurasi: #{keychain_name}")

    # Simulasi eksekusi Gym untuk pipeline headless
    gym(
      scheme: "AppEnterprise",
      clean: true,
      skip_package_ipa: true, # Diaktifkan untuk testing hands-on tanpa biner fisik
      export_method: "app-store"
    )

    delete_keychain(name: keychain_name)
    UI.success("Infrastruktur signing dibersihkan.")
  end
end
```

#### Langkah 4: Validasi Sintaks dan Integrasi Fastlane
Jalankan perintah pengujian sintaks Fastlane di shell:
```bash
bundle exec fastlane lanes
```
Pastikan `ios build_production` muncul pada daftar lane tanpa error Ruby runtime.

---

### 13. Exercise

#### Tingkat: Easy
1. Modifikasi `fastlane/Fastfile` untuk menambahkan lane `increment_patch_version` yang secara otomatis menaikkan versi patch Semantic Versioning (misal: 1.0.0 -> 1.0.1) menggunakan action bawaan Fastlane, lalu simpan perubahan versi tersebut ke dalam git commit baru.

#### Tingkat: Medium
2. Konfigurasikan dynamic provisioning profile mapping pada action `gym` di mana terdapat dua target: Target utama `com.enterprise.app` dan Notification Extension `com.enterprise.app.NotificationService`. Buat `Matchfile` dan pemanggilan `match` yang mengambil sertifikat keduanya dalam satu baris instruksi yang atomik dan aman untuk CI.

#### Tingkat: Hard
3. Buat sebuah kustom Fastlane Plugin atau Ruby Script yang bertindak sebagai *Post-Processing Quality Gate*. Script ini harus:
   * Membaca file coverage laporan JUnit XML dari `test_output/`.
   * Menghitung persentase code coverage total.
   * Melempar exception fatal (`UI.user_error!`) yang membatalkan seluruh proses deployment jika total line coverage berada di bawah 80% sebelum lane `build_app` dieksekusi.

---

### 14. Challenge

**Skenario**:
Anda ditunjuk sebagai Principal iOS Infrastructure Engineer di sebuah startup unicorn yang baru saja mengakuisisi 3 aplikasi iOS terpisah. Masing-masing aplikasi menggunakan sistem code signing yang berbeda: satu menggunakan sertifikat manual berbasis Keychain developer lokal, satu menggunakan script sh custom berbasis OpenSSL, dan satu lagi menggunakan Xcode Managed Signing. 

Waktu kompilasi rata-rata per repo adalah 45 menit, dan insinyur sering mengalami error otentikasi Apple ID karena sistem keamanan 2FA internal perusahaan mengunci akun developer shared.

**Tugas Arsitektur Anda**:
Rancang dokumen arsitektur dan cetak biru pipeline implementasi teknis (tanpa solusi instan *copy-paste*) yang mencakup:
1. Strategi migrasi menyeluruh dari ketiga sistem tersebut ke **Fastlane Match** terpadu menggunakan backend **AWS S3 / Google Cloud Storage** dengan otentikasi berbasis IAM/OIDC (bukan Git SSH deploy keys) untuk memitigasi risiko keamanan repository source control.
2. Desain topologi caching multi-tier (DerivedData persisten, CocoaPods / SPM pre-built binaries via cache layer) untuk memotong build time dari 45 menit ke bawah 12 menit.
3. Strategi otomatisasi penuh App Store Connect API Key (`.p8`) yang mendukung *Zero Trust Runner*, termasuk mekanisme rotasi kunci API secara berkala dan teknik pengisolasian kredensial agar tidak terekspos ke log build CI.

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic (Pilihan Ganda)
1. Apa fungsi utama berkas `.mobileprovision` pada ekosistem kompilasi biner iOS?
   * A. Mengompilasi kode Swift ke dalam format biner Mach-O.
   * B. Mengikat sertifikat kriptografis, kapabilitas Entitlements, Bundle ID, dan daftar UDID target ke dalam satu dokumen terverifikasi Apple.
   * C. Menyimpan aset gambar dan storyboard aplikasi ke dalam bentuk biner terkompresi.
   * D. Menangani komunikasi runtime antara aplikasi dan server backend.

2. Mengapa otentikasi berbasis App Store Connect API Key (`.p8`) lebih disukai pada pipeline CI/CD enterprise dibanding Apple ID standar?
   * A. Karena file `.p8` mempercepat proses kompilasi Swift compiler hingga dua kali lipat.
   * B. Karena file `.p8` menggunakan JWT *stateless* tanpa membutuhkan interaksi Two-Factor Authentication (2FA) SMS/Push yang memblokir proses headless.
   * C. Karena akun Apple ID biasa tidak diizinkan mengunggah file `.ipa` ke TestFlight.
   * D. Karena file `.p8` dapat memotong proses review App Store secara otomatis.

3. Apa yang dilakukan perintah `bundle exec` sebelum mengeksekusi instruksi Fastlane?
   * A. Mengunduh framework Xcode terbaru dari server Apple.
   * B. Memastikan Fastlane berjalan menggunakan dependensi versi pasti yang terkunci di dalam berkas `Gemfile.lock`.
   * C. Menghapus seluruh file sampah di folder DerivedData secara rekursif.
   * D. Memvalidasi lisensi software iOS Enterprise Developer Program.

4. Apa dampak penggunaan flag `readonly: true` pada pemanggilan action `match` di lingkungan CI/CD?
   * A. Mencegah pipeline CI membuat sertifikat atau profil baru di portal developer Apple jika sertifikat yang cocok tidak ditemukan.
   * B. Menjadikan biner `.ipa` bersifat read-only sehingga tidak dapat diubah oleh attacker.
   * C. Menolak akses baca developer terhadap berkas `Fastfile`.
   * D. Menginstruksikan Git untuk tidak melakukan `checkout` pada commit terbaru.

5. File sistem macOS mana yang diakses oleh `security` command-line tool untuk menyimpan sertifikat dan private key saat proses signing biner?
   * A. `/System/Library/CoreServices/`
   * B. Berkas `.xcarchive`
   * C. macOS Keychain (`.keychain-db`)
   * D. SQLite Database Safari

#### Bagian 2: Intermediate (Analisis Log & Solusi Singkat)
1. Analisis log error CI berikut:
   ```text
   [!] Error building the application: Provisioning profile "match AppStore com.org.client" doesn't match the entitlements file's value for the aps-environment entitlement.
   ```
   Jelaskan akar masalahnya dan bagaimana memperbaikinya menggunakan Fastlane!
2. Mengapa pada environment headless CI kita harus membuat *ephemeral keychain* baru dan tidak menggunakan *login.keychain* bawaan macOS runner?
3. Sebutkan perbedaan fundamental antara tool `gym` (`build_app`) dan eksekusi langsung `xcodebuild archive`!
4. Jelaskan peran variabel lingkungan `MATCH_PASSWORD` dalam arsitektur enkripsi Fastlane Match!
5. Bagaimana cara kerja caching SPM di GitHub Actions runner dan kondisi apa yang menyebabkan cache tersebut tidak valid (*invalidated*)?

#### Bagian 3: Skenario Kasus Produksi
1. **Skenario 1 (Pipeline Stalling)**:
   Sebuah pipeline GitHub Actions macOS Runner terhenti secara senyap (*hang*) selama 60 menit tepat pada langkah `build_app`, lalu dibatalkan oleh timeout sistem. Di log lokal, build berjalan normal. Apa dugaan kuat penyebab kebuntuan ini di environment headless dan langkah apa yang wajib diterapkan pada `Fastfile` untuk memperbaikinya?
2. **Skenario 2 (The Multi-Client Deployment Disaster)**:
   Perusahaan Anda merilis update serentak untuk 10 aplikasi whitelabel. Lima aplikasi pertama berhasil di-deploy, namun lima aplikasi berikutnya gagal dengan error HTTP 429 (Too Many Requests) dari App Store Connect API. Desain arsitektur retry dan queueing seperti apa yang harus Anda terapkan pada level Fastlane orchestration?
3. **Skenario 3 (Emergency Hotfix Deployment)**:
   Terjadi bug fatal di versi produksi yang menyebabkan aplikasi perbankan langsung *crash on launch* bagi 100% pengguna. Anda harus merilis hotfix biner dalam waktu kurang dari 30 menit. Deskripsikan alur bypass CI/CD, mekanisme manipulasi build number otomatis, dan konfigurasi *Phased Release* via Fastlane `deliver` untuk mitigasi krisis ini secara terkontrol!

---

### 16. Summary

Implementasi CI/CD iOS pada skala enterprise membutuhkan abstraksi otomasi tingkat tinggi yang mengeliminasi seluruh interaksi manual. Kunci stabilitas pipeline modern berpusat pada:

1. **Integritas Identitas Kriptografis**: Menggunakan **Fastlane Match** dengan backend penyimpanan cloud terenkripsi untuk mengelola sertifikat dan profil distribusi sebagai *Single Source of Truth*.
2. **Stateless Headless Authentication**: Memanfaatkan **App Store Connect API Key (`.p8`)** via format JWT guna menjamin komunikasi mesin-ke-mesin yang terisolasi dari friksi autentikasi dua faktor manual.
3. **Isolasi Lingkungan Eksekusi**: Membangun dan meruntuhkan **Ephemeral Keychains** dinamis per job build guna mencegah *permission lock* serta kebocoran kredensial privat.
4. **Efisiensi Skala Besar**: Mengombinasikan paralelisasi runner (matrix builds), dependensi yang terkunci secara deterministik melalui Bundler, dan caching DerivedData/SPM multi-lapisan untuk menjaga kecepatan deployment di level tertinggi.