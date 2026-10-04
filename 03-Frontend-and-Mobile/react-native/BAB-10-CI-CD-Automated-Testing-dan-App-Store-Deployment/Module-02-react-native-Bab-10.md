# Kurikulum Enterprise: React Native
## Kategori: 03-Frontend-and-Mobile
### BAB 10: CI/CD, Automated Testing, dan App Store Deployment
#### Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objectives
Setelah menyelesaikan modul ini, Principal Engineer / Mobile Architect diharapkan mampu:
- Merancang dan mengoperasikan arsitektur CI/CD berskala enterprise untuk React Native berbasis **Dual-Track Release Model** (Binary Release vs. Over-The-Air Update).
- Mengorkestrasi manajemen sertifikat dan *code signing* multi-platform secara deterministik menggunakan Fastlane (`match`, `gym`, `supply`) dengan enkripsi terdistribusi.
- Mengimplementasikan pipeline pengujian terotomatisasi bertingkat (Unit, Component, Hermes Bytecode Verification, dan E2E Black-Box Testing via Maestro/Detox) pada cloud runners.
- Mengonfigurasi distribusi otomatis ke TestFlight dan Google Play Console (Internal/Production tracks) dengan strategi *staged rollout* bertahap serta automasi *symbolication mapping* (dSYM dan ProGuard/R8) ke sistem pemantauan observabilitas (Sentry/Datadog).
- Menganalisis trade-off performa, biaya, dan keamanan antara Cloud vs Self-Hosted CI Runners (macOS/Linux) serta memitigasi risiko *runtime crash* pada ekosistem hybrid native-JS.

---

### 2. Prerequisites
Sebelum mendalami modul ini, peserta wajib menguasai:
- **React Native Architecture**: Memahami New Architecture (Fabric, TurboModules, Hermes Engine, Codegen).
- **Native Toolchain**: Xcode build system (Schemes, Configurations, Provisioning Profiles), Gradle execution lifecycle (Flavors, Build Types, Signing Configurations).
- **Core Automation**: Bash/Zsh scripting lanjutan, Ruby syntax dasar (untuk konfigurasi Fastfile).
- **DevOps & Cloud**: Git branching model (GitFlow / Trunk-Based Development), GitHub Actions / GitLab CI declarative syntax, serta Public Key Cryptography (GPG/OpenSSL, SSH).

---

### 3. Concept & Internal Architecture

Arsitektur rilis React Native enterprise memisahkan artefak menjadi dua lapisan siklus hidup: **Native Binary Layer** dan **Dynamic JavaScript/Hermes Bytecode Layer**.

```
+-----------------------------------------------------------------------------------+
|                        REACT NATIVE ARTIFACT COMPOSITION                          |
+-----------------------------------------------------------------------------------+
|  [Native Binary Shell (Slow Track: 1-2 Minggu)]                                    |
|   - iOS: Mach-O Executable + Frameworks + Assets + Pods                           |
|   - Android: Dalvik/ART Executable (.dex) + Shared Libraries (.so) + Manifest     |
|   - Native Code Signing: Apple Developer Certificates & Android Keystore (v2/v3)  |
|                                                                                   |
|  [Dynamic Runtime Layer (Fast Track: On-Demand / Jam)]                             |
|   - Compiled Hermes Bytecode (HBC)                                                |
|   - Static Assets (Images, Fonts, Localized JSON)                                 |
|   - OTA Metadata & Target Runtime Constraints (SemVer Semantics)                  |
+-----------------------------------------------------------------------------------+
```

#### Dual-Track Release Model
1. **Binary Track (Native Engine Updates)**:
   - Dijalankan saat ada perubahan pada direktori `ios/` atau `android/`, pembaruan dependensi native (C++/Java/Kotlin/Obj-C), modifikasi `Info.plist`/`AndroidManifest.xml`, atau pembaruan mayor React Native core.
   - Melibatkan kompilasi penuh native via Xcode CLI (`xcodebuild`) dan Gradle Wrapper (`gradlew assembleRelease` / `bundleRelease`).
   - Wajib melalui siklus peninjauan resmi (App Store Review & Google Play Policy Review).

2. **OTA Update Track (JS/Asset Patching)**:
   - Dijalankan untuk *bug fixing* logika bisnis React, pembaruan UI berbasis styling/komponen, atau penyesuaian aset statis.
   - React Native Metro bundler mengekstrak Abstract Syntax Tree (AST), melakukan *tree-shaking*, dan mengompilasi JavaScript ke Hermes Bytecode (`hermesc`).
   - Artefak di-*pack* ke format bundle terenkripsi lalu didistribusikan melalui Content Delivery Network (CDN) OTA Engine (misal: EAS Update / CodePush).
   - Bundle dimuat secara dinamis saat *runtime* tanpa perlu melalui proses validasi ulang toko aplikasi (selama mematuhi Apple App Store Review Guideline 2.5.2).

#### Code Signing Cryptography & Certificate Governance
- **iOS Signing**: Menggunakan konsep *public-key cryptography* Apple. Sertifikat distribusi (`.cer` / `.p12`) memvalidasi identitas penerbit, sedangkan *Provisioning Profile* (`.mobileprovision`) mengikat sertifikat, App ID, Entitlements (misal: Push Notifications, Associated Domains), dan Device UDIDs (untuk Ad-Hoc/Development). Fastlane `match` menerapkan metodologi *Git-based source of truth* terenkripsi AES-256 untuk membagikan satu profil deterministik ke seluruh tim dan CI runner, mencegah *certificate explosion*.
- **Android Signing**: Menggunakan Android App Bundle (AAB) dengan Google Play App Signing. Mesin CI menandatangani AAB menggunakan *Upload Key* (PKCS#12 / JKS). Google memverifikasi tanda tangan Upload Key, menghapus wrapper AAB, mengoptimalkan APK split (screen density, ABI, language), dan menandatanganinya kembali dengan *Application Signing Key* privat yang tersimpan di Google Cloud KMS sebelum didistribusikan ke perangkat pengguna.

#### Hermes Bytecode Compilation & Runtime Safety
Kompilasi JS menjadi Hermes Bytecode (`.hbc`) dilakukan di level CI, bukan di perangkat klien:
$$\text{Source Code (JS/TS)} \xrightarrow{\text{Metro}} \text{Single Minified JS} \xrightarrow{\text{hermesc -emit-binary}} \text{Hermes Bytecode (HBC)}$$
Setiap versi Hermes memiliki struktur versi bytecode biner tertentu (`Hermes Bytecode Version`). Runner CI harus mengompilasi bytecode dengan toolchain `hermesc` yang identik dengan versi runtime engine Hermes native yang tersemat pada binary terpasang. Ketidakcocokan versi bytecode akan memicu *instant fatal crash* saat aplikasi diinisialisasi.

---

### 4. Why & What

| Dimensi | Manual Mobile Release (Ad-Hoc) | Automated Enterprise Pipeline |
| :--- | :--- | :--- |
| **Keamanan Kunci** | Kunci Keystore & Profil tersimpan di laptop lokal pengembang; risiko kebocoran tinggi. | Kunci disimpan di Secrets Manager / Vault; dienkripsi *in-rest* & *in-transit*; rotasi otomatis. |
| **Konsistensi Build** | "It works on my machine" akibat perbedaan versi Xcode, Node, CocoaPods, atau JDK. | Ephemeral containerized/virtualized environments; deterministik dan dapat direproduksi 100%. |
| **Tracing Simbolik** | File `dSYM` dan `mapping.txt` hilang/lupa diunggah; *crash reports* di produksi menjadi kode anonim (*un-symbolicated*). | Ekstraksi dan pengunggahan otomatis seluruh artefak debug symbols ke crash analytics (Sentry/Datadog) terintegrasi build pipeline. |
| **Waktu Rilis** | 4-8 jam kerja rekayasa manual per platform; rentan kesalahan manusia saat deployment. | Zero-Touch Deployment; satu git tag memicu eksekusi multi-platform paralel; rilis selesai dalam menit. |

---

### 5. How (Workflow Detail)

Alur kerja CI/CD enterprise React Native berjalan melalui *multi-tier gate*:

```
[Developer Push / PR] 
        │
        ├──> Gate 1: Code Verification (Linux Runner)
        │      ├── Static Analysis: ESLint, TypeScript Compiler (tsc --noEmit)
        │      ├── Security Audit: Dependency vulnerability check
        │      └── Unit & Integration Tests: Jest + React Native Testing Library
        │
        ├──> Gate 2: Hermes Bytecode Build Check (Linux Runner)
        │      └── Metro bundling dry-run & hermesc validation
        │
[Merge to main / Tagging: vX.Y.Z]
        │
        ├──> Gate 3: Native Build & E2E Validation
        │      ├── [Matrix: Android Runner (Ubuntu)]
        │      │     ├── Gradle cache restore
        │      │     ├── Build Debug APK
        │      │     └── Maestro E2E Regression Smoke Tests
        │      └── [Matrix: iOS Runner (macOS M-series)]
        │            ├── CocoaPods cache restore
        │            ├── Build Simulator App
        │            └── Maestro E2E Regression Smoke Tests
        │
        ├──> Gate 4: Code Signing & Release Compilation
        │      ├── Android: Build AAB Release signed via Play Store Upload Key
        │      └── iOS: Fastlane Match sync & Gym AOT-compilation (IPA)
        │
        ├──> Gate 5: Observability Artifact Ingestion
        │      ├── Upload ProGuard/R8 mapping.txt to Crash Reporting
        │      └── Upload native dSYM files to Crash Reporting
        │
        └──> Gate 6: Target Distribution
               ├── Google Play Console: Internal App Sharing -> Production (Phased: 10% -> 50% -> 100%)
               └── App Store Connect: TestFlight -> Phased Rollout (7 Days Automatic Release)
```

---

### 6. Analogy & Diagram ASCII

#### Analogi Konseptual
Bayangkan perilisan aplikasi seperti mengoperasikan **Layanan Kereta Cepat Listrik**:
- **Binary Release** adalah **Pembangunan Jalur Rel & Kereta Fisik Baru**: Memerlukan inspeksi keselamatan ketat dari otoritas perhubungan (App Store Review), pengelasan rel baja (Native Compilation), dan memakan waktu berhari-hari sebelum izin operasi keluar.
- **OTA Updates** adalah **Pergantian Informasi Layar Digital & Penataan Interior**: Mengubah peta rute, memperbarui brosur, atau mengganti warna kursi di dalam gerbong yang sudah berjalan. Dilakukan secara instan semalam tanpa harus menghentikan atau mengganti unit kereta api fisik dari lintas rel.

#### Diagram Arsitektur CI/CD Paripurna

```
+----------------------------------------------------------------------------------------------------+
|                                    ENTERPRISE CI/CD ENGINE                                         |
+----------------------------------------------------------------------------------------------------+
       │
       ▼
+-----------------------+      Webhook       +-------------------------------------------------------+
|  VCS (GitHub/GitLab)  | ─────────────────> | GitHub Actions / GitLab Orchestrator                  |
+-----------------------+                    +-------------------------------------------------------+
                                                                     │
                         ┌───────────────────────────────────────────┴───────────────────────────────────────────┐
                         ▼                                                                                       ▼
         +-------------------------------+                                                       +-------------------------------+
         |       Android Pipeline        |                                                       |         iOS Pipeline          |
         |        (Ubuntu-latest)        |                                                       |        (macOS-latest)         |
         +-------------------------------+                                                       +-------------------------------+
                         │                                                                                       │
                         ├─ Gradle Cache Engine                                                                  ├─ CocoaPods / SPM Cache
                         ├─ Build .aab (Release)                                                                 ├─ Fastlane match (Sync Certs)
                         ├─ R8 Optimization & Obfuscation                                                        ├─ Fastlane gym (xcodebuild)
                         ├─ Extract mapping.txt                                                                  ├─ Extract .dSYM Bundles
                         │                                                                                       │
                         ▼                                                                                       ▼
         +-------------------------------+                                                       +-------------------------------+
         |    Google Play Developer API  |                                                       |    App Store Connect API      |
         +-------------------------------+                                                       +-------------------------------+
                         │                                                                                       │
                         ├─ Target: Internal / Phased Release                                                    ├─ Target: TestFlight / Phased
                         │                                                                                       │
                         └───────────────────────────────────────────┬───────────────────────────────────────────┘
                                                                     │
                                                                     ▼
                                                     +-------------------------------+
                                                     |    Crash Reporting Platform   |
                                                     |     (Sentry / Bugsnag CLI)    |
                                                     +-------------------------------+
                                                     | Ingest:                       |
                                                     | - JS Source Maps              |
                                                     | - Hermes Bytecode debug info  |
                                                     | - ProGuard mapping.txt        |
                                                     | - Mach-O dSYM archives        |
                                                     +-------------------------------+
```

---

### 7. Simple Example & Practical Example

#### Implementasi Praktis: Fastfile Skala Industri (`ios/fastlane/Fastfile` & `android/fastlane/Fastfile`)

##### Konfigurasi Fastlane iOS (`ios/fastlane/Fastfile`):
```ruby
default_platform(:ios)

platform :ios do
  desc "Push new production build to TestFlight & App Store with Automated Symbolication"
  lane :build_and_deploy_production do |options|
    ensure_git_status_clean
    
    # 1. Autentikasi API Key App Store Connect (Zero-Touch)
    api_key = app_store_connect_api_key(
      key_id: ENV["ASC_KEY_ID"],
      issuer_id: ENV["ASC_ISSUER_ID"],
      key_content: ENV["ASC_KEY_CONTENT"],
      is_key_content_base64: true
    )

    # 2. Sinkronisasi Profil dan Sertifikat Terenkripsi
    match(
      type: "appstore",
      readonly: is_ci,
      app_identifier: ["com.enterprise.app"],
      api_key: api_key,
      git_url: ENV["MATCH_GIT_URL"]
    )

    # 3. Sinkronisasi Versi dari Git Tag atau Argumen CI
    increment_build_number(
      build_number: options[:build_number] || ENV["GITHUB_RUN_NUMBER"]
    )
    
    # 4. Kompilasi Native Binary (.ipa)
    gym(
      scheme: "EnterpriseApp",
      workspace: "EnterpriseApp.xcworkspace",
      output_directory: "./build",
      output_name: "EnterpriseApp.ipa",
      export_method: "app-store",
      clean: true,
      include_symbols: true,
      include_bitcode: false
    )

    # 5. Ingest Native dSYMs ke Sentry
    sentry_upload_dif(
      auth_token: ENV["SENTRY_AUTH_TOKEN"],
      org_slug: "enterprise-core",
      project_slug: "react-native-app",
      path: "./build/EnterpriseApp.app.dSYM.zip"
    )

    # 6. Distribusi ke TestFlight dengan Deployment Phased 
    pilot(
      api_key: api_key,
      ipa: "./build/EnterpriseApp.ipa",
      skip_waiting_for_build_processing: true,
      distribute_external: false
    )
  end
end
```

##### Konfigurasi Pipeline GitHub Actions (`.github/workflows/deploy-production.yml`):
```yaml
name: Mobile Enterprise Production Pipeline

on:
  push:
    tags:
      - 'v[0-9]+.[0-9]+.[0-9]+'

concurrency:
  group: production-deploy-${{ github.ref }}
  cancel-in-progress: false

jobs:
  validate-js:
    name: Validate JS & Hermes Bundle
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js Environment
        uses: actions/setup-node@v4
        with:
          node-version: 20.x
          cache: 'yarn'

      - name: Install Dependencies
        run: yarn install --frozen-lockfile

      - name: Static Type Check & Linting
        run: |
          yarn tsc --noEmit
          yarn eslint . --max-warnings 0

      - name: Unit & Component Tests
        run: yarn jest --ci --coverage --maxWorkers=2

      - name: Dry-run Hermes Compilation
        run: |
          mkdir -p /tmp/hermes-check
          yarn react-native bundle \
            --platform android \
            --dev false \
            --entry-file index.js \
            --bundle-output /tmp/hermes-check/index.android.bundle \
            --assets-dest /tmp/hermes-check
          node_modules/react-native/sdks/hermesc/linux64-bin/hermesc \
            -emit-binary \
            -out /tmp/hermes-check/index.android.hbc \
            /tmp/hermes-check/index.android.bundle

  build-android:
    name: Build & Release Android
    needs: validate-js
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup JDK
        uses: actions/setup-java@v4
        with:
          distribution: 'zulu'
          java-version: '17'
          cache: 'gradle'

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 20.x
          cache: 'yarn'

      - name: Install Dependencies
        run: yarn install --frozen-lockfile

      - name: Decode Android Keystore
        run: |
          echo "${{ secrets.ANDROID_UPLOAD_KEYSTORE_BASE64 }}" | base64 --decode > android/app/upload.keystore

      - name: Build Android App Bundle (AAB) & Upload to Play Store
        working-directory: android
        env:
          KEYSTORE_PASSWORD: ${{ secrets.ANDROID_KEYSTORE_PASSWORD }}
          KEY_ALIAS: ${{ secrets.ANDROID_KEY_ALIAS }}
          KEY_PASSWORD: ${{ secrets.ANDROID_KEY_PASSWORD }}
          PLAY_STORE_JSON_KEY: ${{ secrets.PLAY_STORE_JSON_KEY }}
          SENTRY_AUTH_TOKEN: ${{ secrets.SENTRY_AUTH_TOKEN }}
        run: |
          bundle install
          bundle exec fastlane android deploy_play_store build_number:${{ github.run_number }}

  build-ios:
    name: Build & Release iOS
    needs: validate-js
    runs-on: macos-14
    steps:
      - uses: actions/checkout@v4

      - name: Select Xcode 15.x
        run: sudo xcode-select -switch /Applications/Xcode_15.4.app

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: 20.x
          cache: 'yarn'

      - name: Setup Ruby
        uses: ruby/setup-ruby@v1
        with:
          ruby-version: '3.2'
          bundler-cache: true
          working-directory: ios

      - name: Install JS Dependencies
        run: yarn install --frozen-lockfile

      - name: Cache CocoaPods Pods
        uses: actions/cache@v4
        with:
          path: ios/Pods
          key: ${{ runner.os }}-pods-${{ hashFiles('ios/Podfile.lock') }}
          restore-keys: |
            ${{ runner.os }}-pods-

      - name: Install Pods
        working-directory: ios
        run: pod install --repo-update

      - name: Run Fastlane iOS Deploy
        working-directory: ios
        env:
          ASC_KEY_ID: ${{ secrets.ASC_KEY_ID }}
          ASC_ISSUER_ID: ${{ secrets.ASC_ISSUER_ID }}
          ASC_KEY_CONTENT: ${{ secrets.ASC_KEY_CONTENT }}
          MATCH_GIT_URL: ${{ secrets.MATCH_GIT_URL }}
          MATCH_PASSWORD: ${{ secrets.MATCH_PASSWORD }}
          SENTRY_AUTH_TOKEN: ${{ secrets.SENTRY_AUTH_TOKEN }}
          GITHUB_TOKEN: ${{ secrets.PERSONAL_ACCESS_TOKEN_FOR_MATCH }}
        run: |
          bundle exec fastlane ios build_and_deploy_production build_number:${{ github.run_number }}
```

---

### 8. Real World Case Study (Enterprise Scale)

**Konteks**: Aplikasi FinTech dengan skala 15+ juta Monthly Active Users (MAU) dan 70 insinyur perangkat lunak yang tersebar pada 6 *feature teams*.
**Masalah**: 
1. Frekuensi rilis native 2 mingguan kerap tertunda hingga 5 hari kerja akibat kegagalan sinkronisasi sertifikat provisi pengembang dan tabrakan versi *build number*.
2. Tingkat pelaporan error native (Crash-free users) drop ke 98.1% pasca deployment akibat dSYM tidak terunggah secara otomatis, menyebabkan debug terhambat 48 jam karena *un-symbolicated stack traces*.
3. Kerentanan fatal ditemukan pada flow transfer dana; proses perbaikan bug native darurat via Google Play Review membutuhkan waktu 18 jam, mengekspos risiko kepatuhan perbankan.

**Solusi Arsitektur Produksi**:
1. **Centralized Deterministic Signing**: Mengimplementasikan Fastlane `match` yang disimpan dalam private Git repo dengan rotasi kunci berkala berbasis Google Cloud KMS. Seluruh insinyur lokal kehilangan akses ekspor kunci produksi manual; hanya *ephemeral runner* CI yang dapat mendekripsi sertifikat saat eksekusi tag.
2. **Dual-Release Governance Engine**:
   - Menerapkan **CodePush/EAS Update Rollout Rules**: Pengecekan versi bundle menggunakan Semantic Versioning eksplisit (`targetBinaryVersion: ~3.4.0`).
   - Membuat *Automated Symbolication Bridge*: Langkah kompilasi secara atomik memadukan ekstraksi ProGuard/R8 dan dSYM; jika langkah pengunggahan artefak observabilitas gagal, pipeline secara otomatis menghentikan (*fail-closed*) pengiriman binary ke toko aplikasi.
3. **Automated Phased Deployment with Guardrails**:
   - Google Play: Rollout bertahap otomatis (Day 1: 5%, Day 2: 10%, Day 3: 20%, Day 4: 50%, Day 5: 100%).
   - Pemantauan metrik crash secara terprogram via Datadog/Sentry Webhook. Jika crash rate rilis baru > 0.05%, pipeline memicu script internal API Google Play untuk membatalkan rollout (*halt rollout*) secara otomatis.

**Hasil**:
- Crash-free session terjaga pada **99.94%**.
- Lead time perbaikan bug JS kritis dipangkas dari **18 jam menjadi 12 menit** menggunakan OTA Updates.
- Biaya siklus rilis (*engineering hours spent*) turun 82%.

---

### 9. Trade-offs & Engineering Decisions

#### A. CI Runner Strategy: Cloud Runners vs. Self-Hosted Mac Hardware
- **GitHub-Hosted macOS Runners**:
  - *Pros*: Tanpa biaya pemeliharaan hardware, konfigurasi isolasi lingkungan total (*zero state pollution*), rotasi OS instan.
  - *Cons*: Sangat mahal ($0.08 - $0.16 per menit untuk instances Apple Silicon), waktu antrean build tinggi pada jam kerja sibuk, latensi caching tinggi saat transfer data gigabytes.
- **Self-Hosted Bare-Metal Mac Farm (e.g., Mac Studio M2 Max / Mac Mini Clusters)**:
  - *Pros*: Waktu build kompilasi native 3x lebih cepat (eksekusi lokal 8-12 menit vs 35 menit di cloud standard), *cost-efficient* untuk frekuensi kompilasi tinggi (>50 build/hari).
  - *Cons*: Membutuhkan tim dedicated untuk patching macOS/Xcode, risiko *state leakage* antar build, isolasi jaringan rumit untuk mitigasi security exposure.

#### B. Automated E2E Testing: Detox vs. Maestro
- **Detox (White-Box Synchronization)**:
  - *Mekanisme*: Berjalan di dalam proses aplikasi; menggunakan internal synchronization loops (Espresso/EarlGrey) untuk mendeteksi status idle dari React Native bridge/Hermes thread.
  - *Trade-off*: Sangat stabil terhadap flakiness animasi, namun konfigurasi kompleks pada New Architecture (Fabric) dan sulit memvalidasi interaksi native di luar konteks aplikasi (misal: Push Notifications tray, modal izin OS sistem).
- **Maestro (Black-Box Accessibility-Driven)**:
  - *Mekanisme*: Berjalan secara eksternal via ADB (Android) dan XCUITest/idb (iOS); membaca accessibility tree dari UI hierarchy.
  - *Trade-off*: Setup sangat mudah, agnostik framework, mendukung pengujian lintas alur OS (misal verifikasi SMS OTP, FaceID mock); namun membutuhkan *polling delay* eksplisit jika sinkronisasi visual terhambat lag jaringan yang berat.

---

### 10. Common Mistakes & Troubleshooting

#### Kesalahan 1: Hermes Bytecode Version Mismatch pada OTA Deployments
* **Gejala**: Pengguna yang menerima update OTA mengalami *crash on startup* (White Screen / App Termination seketika). Logcat menampilkan `Hermes bytecode version mismatch: expected X, got Y`.
* **Akar Masalah**: Runner CI mengompilasi JS bundle menggunakan versi `hermes-engine` NPM yang berbeda dari versi native Hermes yang dikompilasi ke dalam biner yang terdistribusi di pengguna.
* **Solusi**: Terapkan assertion ketat pada CI sebelum rilis OTA. Periksa checksum versi native engine dengan membaca `node_modules/react-native/sdks/hermesc` yang terkunci dalam `yarn.lock`:
```bash
HERMESC_VER=$(./node_modules/react-native/sdks/hermesc/linux64-bin/hermesc -version | head -n 1)
echo "Current Hermes Compiler Engine: $HERMESC_VER"
# Validasi kompatibilitas dengan versi native klien target
```

#### Kesalahan 2: Provisioning Profile Missing Matching Capabilities (Entitlements Drift)
* **Gejala**: Xcode build gagal saat *step* `gym` dengan pesan `Provisioning profile doesn't include the Associated Domains entitlement`.
* **Akar Masalah**: Insinyur menambahkan capability baru (misal Universal Links / Associated Domains) di project Xcode lokal, namun sertifikat provisi di repo Fastlane `match` belum di-regenerasi dengan spesifikasi entitlement baru.
* **Solusi**: Eksekusi perintah pembaruan profil melalui Fastlane secara deterministik:
```bash
bundle exec fastlane match appstore --force --app_identifier "com.enterprise.app"
```

#### Kesalahan 3: Missing R8/ProGuard Rules for React Native Interfaces
* **Gejala**: Android Release APK/AAB berhasil dikompilasi, namun saat dibuka di perangkat, aplikasi crash dengan error `ClassNotFoundException` atau `NoSuchMethodError` pada TurboModules.
* **Akar Masalah**: R8 minifier secara keliru melakukan *stripping* terhadap class C++ JNI bridge atau Java TurboModules karena dianggap tidak terpakai oleh static code analysis.
* **Solusi**: Pertahankan interface native di `android/app/proguard-rules.pro`:
```proguard
# Menjaga arsitektur dasar React Native & JNI bridge
-keep class com.facebook.react.** { *; }
-keep class com.facebook.jni.** { *; }
-keep class com.facebook.hermes.** { *; }
-keepclassmembers class * {
    @com.facebook.react.bridge.ReactMethod *;
    @com.facebook.react.bridge.ReactProperty *;
}
-keepattributes *Annotation*
```

---

### 11. Best Practices (Production Checklist)

1. **Security & Secrets Governance**:
   - [ ] Tidak ada plain text credentials (`.p12`, `.keystore`, API keys) di Git history.
   - [ ] Akses App Store Connect menggunakan App Store Connect API Key (JWT), bukan Apple ID berbasis user yang memerlukan 2FA SMS.
   - [ ] Keystore Android dilindungi oleh master key berbasis PKCS#12 yang diinjeksi via Secret Environment runtime.
2. **Determinisme Dependency & Build Environment**:
   - [ ] Mengunci dependency native menggunakan `Gemfile.lock` (Fastlane & CocoaPods), `yarn.lock` atau `pnpm-lock.yaml`, dan Gradle lockfiles.
   - [ ] Xcode command line tools dikunci menggunakan `xcode-select` ke sub-versi spesifik (misal `15.4`) di CI agent.
3. **Observabilitas dan Release Safety**:
   - [ ] Setiap build production mengunggah dSYM dan mapping ProGuard ke Crash Analytics secara atomik.
   - [ ] Mengaktifkan *Phased Rollout* secara *default* (7 hari di iOS, bertahap 5% - 100% di Google Play).
   - [ ] Menjaga *concurrency locks* pada CI pipeline untuk mencegah tabrakan penomoran versi internal build number.
4. **OTA Deployment Safety**:
   - [ ] Gunakan semantic constraints (`~X.Y.Z`) pada rilis OTA, bukan wildcard (`*`), untuk mencegah bundle JS modern tereksekusi pada shell native versi lama.

---

### 12. Hands-on Practice

Siapkan struktur direktori berikut pada proyek Anda:
```bash
mkdir -p hands-on/m02/fastlane hands-on/m02/.maestro
```

#### Langkah 1: Inisialisasi Spesifikasi Deployment Maestro E2E
Buat file `hands-on/m02/.maestro/smoke-test.yaml`:
```yaml
appId: "com.enterprise.app"
---
- launchApp:
    clearState: true
- assertVisible: "Selamat Datang di Portal Enterprise"
- tapOn: "Input Username"
- inputText: "principal.engineer@enterprise.com"
- tapOn: "Input Password"
- inputText: "SecureCredentials#2026"
- tapOn: "Tombol Autentikasi"
- assertVisible: "Dashboard Portofolio"
- stopApp
```

#### Langkah 2: Skrip Automasi Fastlane Android Production
Buat file `hands-on/m02/fastlane/Fastfile`:
```ruby
default_platform(:android)

platform :android do
  desc "Kompilasi AAB dan Unggah ke Google Play Internal Track"
  lane :deploy_internal do |options|
    build_num = options[:build_number] || ENV["GITHUB_RUN_NUMBER"] || "1"
    
    # Konfigurasi versi dan build secara dinamis
    gradle(
      task: "bundle",
      build_type: "Release",
      project_dir: "./android",
      properties: {
        "android.injected.version.code" => build_num,
        "android.injected.signing.store.file" => "upload.keystore",
        "android.injected.signing.store.password" => ENV["KEYSTORE_PASSWORD"],
        "android.injected.signing.key.alias" => ENV["KEY_ALIAS"],
        "android.injected.signing.key.password" => ENV["KEY_PASSWORD"],
      }
    )

    # Ekstraksi dan Validasi Artefak
    aab_path = "./android/app/build/outputs/bundle/release/app-release.aab"
    mapping_path = "./android/app/build/outputs/mapping/release/mapping.txt"

    # Ingest Proguard Mapping ke Observability Platform
    sh("npx @sentry/cli upload-dif --org enterprise --project rn-android --type proguard #{mapping_path}")

    # Distribusi ke Play Store via Google Play API
    upload_to_play_store(
      track: "internal",
      package_name: "com.enterprise.app",
      aab: aab_path,
      json_key_data: ENV["PLAY_STORE_JSON_KEY"],
      skip_upload_images: true,
      skip_upload_screenshots: true
    )
  end
end
```

#### Langkah 3: Eksekusi Pengujian Lokal Pipeline
Jalankan validasi linting Fastfile dan sintaks Maestro di lingkungan development:
```bash
# Validasi sintaks Ruby Fastfile
bundle exec fastlane android deploy_internal --dry-run

# Validasi UI Smoke Test via Maestro CLI pada emulator yang aktif
maestro test hands-on/m02/.maestro/smoke-test.yaml
```

---

### 13. Exercises

#### Level Easy
Konfigurasikan script bash untuk CI yang mengekstrak native version code dari `android/app/build.gradle` dan memvalidasi bahwa `versionName` identik secara strictly-typed dengan field `"version"` di dalam `package.json`. Gagalkan pipeline jika terjadi *version mismatch*.

#### Level Medium
Buat lane Fastlane iOS yang secara otomatis:
1. Mengunduh profil provisi App Store menggunakan `match`.
2. Mengambil angka build number terakhir dari TestFlight menggunakan App Store Connect API.
3. Menginkrementasi angka tersebut sebanyak +1.
4. Mengompilasi binary tanpa harus melakukan git commit baru untuk perubahan versi build.

#### Level Hard
Rancang GitHub Actions Workflow komprehensif yang menerapkan **Dual-Lane CI**:
- Jika push berisi perubahan *hanya* pada direktori `src/` atau `assets/`, pipeline hanya akan mengompilasi Hermes Bytecode, menjalankan Jest, dan memicu OTA Update via CLI ke staging track.
- Jika push mengandung perubahan pada file `ios/`, `android/`, `package.json`, atau `Podfile`, pipeline secara dinamis beralih mengeksekusi kompilasi native biner penuh multi-platform (Android & iOS matrix runner) dan mengunggah artefak ke testing track masing-masing toko aplikasi.

---

### 14. Architecture Challenge

**Skenario**:
Anda adalah Principal Mobile Architect di platform e-commerce dengan GMV triliunan rupiah. Aplikasi Anda mengalami insiden di mana sebuah update OTA mendistribusikan JS Bundle yang mengandung bug sinkronisasi state. Bundle ini menyebabkan memory leak fatal di perangkat low-end Android dan me-restart aplikasi secara terus-menerus (*bootloop crash*). Karena aplikasi langsung crash saat startup, native OTA client di aplikasi tidak pernah sempat menghubungi server untuk mengunduh update perbaikan (Rollback payload).

**Tantangan Arsitektur**:
Rancang arsitektur pertahanan bertingkat (*Fail-Safe Autonomous Recovery Engine*) pada lapisan Native Android & iOS yang memenuhi kriteria berikut:
1. **Detection Mechanism**: Bagaimana native shell mendeteksi secara otonom bahwa JS bundle yang baru diterapkan menyebabkan crash startup berulang tanpa bantuan telemetry cloud (karena proses crash terjadi sebelum HTTP request telemetry sempat dieksekusi)?
2. **Autonomous Safe-Mode Rollback**: Tentukan mekanisme fallback native untuk membatalkan load bundle yang corrupt dan secara instan me-revert eksekusi ke *Embedded Asset Bundle* (base native asset) yang aman.
3. **Blacklisting & Server Sync**: Bagaimana arsitektur mengomunikasikan identitas bundle yang rusak tersebut ke cloud server saat aplikasi berhasil di-recover, guna memastikan perangkat lain tidak mengalami siklus crash yang sama?

*Tuliskan dokumen arsitektur teknis Anda mencakup state-machine, pseudo-code native bridge (Kotlin/Swift), dan sequence diagram alur booting aplikasi.*

---

### 15. Quiz Evaluasi Pemahaman

#### Bagian 1: Basic Concept (Pilihan Ganda)

1. Apa fungsi utama dari tool Fastlane `match` dalam ekosistem pengembangan iOS?
   - A. Melakukan beautify dan format kode Objective-C/Swift.
   - B. Mengelola dan menyinkronkan sertifikat serta provisioning profile secara terenkripsi menggunakan repository Git terpusat.
   - C. Menjalankan parallel testing pada multi-simulator iOS.
   - D. Mengubah kode JavaScript menjadi Hermes bytecode secara otomatis.

2. Mengapa Android App Bundle (`.aab`) lebih direkomendasikan daripada Universal APK (`.apk`) untuk publikasi ke Google Play Console?
   - A. `.aab` tidak memerlukan proses code signing.
   - B. `.aab` memungkinkan kompilasi native C++ berjalan langsung di cloud runner.
   - C. Google Play menggunakan `.aab` untuk menghasilkan APK split yang dioptimalkan sesuai arsitektur CPU, bahasa, dan densitas layar perangkat pengguna.
   - D. `.aab` dapat dieksekusi langsung di perangkat pengembang tanpa perlu di-*extract*.

3. Pada pipeline CI/CD React Native, file apakah yang wajib diunggah ke Sentry/Datadog agar stack trace crash native pada iOS dapat dibaca dengan jelas?
   - A. `Podfile.lock`
   - B. Mach-O dSYM (*Debug Symbol*) files
   - C. `Info.plist`
   - D. `project.pbxproj`

4. Di lapisan manakah OTA Update (seperti CodePush atau EAS Update) beroperasi?
   - A. Memperbarui implementasi TurboModules C++ pada native runtime.
   - B. Memperbarui JavaScript runtime bundle dan static assets secara in-memory / storage lokal.
   - C. Mengubah versi compiler LLVM pada runtime.
   - D. Menambahkan System Permissions pada `AndroidManifest.xml`.

5. Apa kegunaan utama dari *Hermes Bytecode pre-compilation* saat proses build di CI server?
   - A. Menghapus kebutuhan pengujian Jest.
   - B. Mempercepat waktu startup aplikasi (Time-To-Interactive) di perangkat klien karena parsing JS tidak lagi dilakukan saat runtime.
   - C. Mengenkripsi kode native Kotlin/Swift agar tidak dapat di-reverse engineer.
   - D. Mengurangi ukuran download binary iOS sebesar 90%.

---

#### Bagian 2: Intermediate Architectural (Analisis Kasus)

6. Sebuah pipeline CI/CD GitHub Actions menggunakan runner `macos-latest` untuk membuild iOS. Pipeline memakan waktu 45 menit, di mana 25 menit dihabiskan pada step `pod install`. Langkah arsitektur paling efektif untuk memangkas waktu build tersebut secara radikal adalah:
   - A. Menghapus CocoaPods dan mengganti seluruh library menggunakan import manual C++.
   - B. Mengimplementasikan caching folder `ios/Pods` yang divalidasi menggunakan hash dari file `ios/Podfile.lock`.
   - C. Menjalankan pod install dengan flag `--verbose`.
   - D. Mematikan fitur Hermes pada `Podfile`.

7. Jika Anda merilis OTA update yang mengandung pemanggilan method TurboModule baru yang belum ada pada versi binary native yang terpasang di perangkat user, apa yang akan terjadi?
   - A. Native shell akan mendownload implementasi method native secara otomatis dari remote CDN.
   - B. Aplikasi akan mengabaikan pemanggilan fungsi tersebut secara diam-diam.
   - C. Terjadi fatal unhandled runtime exception (`TypeError: Cannot read property of undefined` atau native NULL pointer exception) yang memicu crash aplikasi seketika.
   - D. Google Play Store akan memblokir bundle OTA tersebut sebelum mencapai perangkat.

8. Dalam konfigurasi Fastlane, apa fungsi perintah `ensure_git_status_clean` sebelum menjalankan automated deployment lane?
   - A. Menghapus seluruh file git untracked di disk developer.
   - B. Memastikan tidak ada modifikasi kode yang tidak ter-commit di working directory CI agent agar artefak yang dibuild 100% identik dengan commit hash git target.
   - C. Mengunduh commit terbaru dari branch default secara paksa.
   - D. Memeriksa apakah akses personal token pengembang masih aktif.

9. Manakah pernyataan yang benar mengenai strategi App Store Connect API Key berbasis JWT dibandingkan penggunaan otentikasi Apple ID tradisional pada Fastlane?
   - A. App Store Connect API Key memerlukan validasi interaktif 2-Factor Authentication (2FA) SMS setiap 30 hari.
   - B. JWT API Key bersifat statis, headless, tidak kedaluwarsa oleh session cookies, dan tidak terhambat oleh verifikasi 2FA SMS interaktif di CI server.
   - C. Apple ID tradisional lebih aman karena tidak memerlukan secrets tersimpan di CI runner.
   - D. API Key hanya dapat digunakan untuk mendistribusikan aplikasi macOS, bukan iOS.

10. Mengapa rilis OTA yang mengubah aset native (seperti menambahkan permission kamera pada Android atau merombak icon native) dilarang secara arsitektur dan teknis?
    - A. Karena CDN OTA tidak memiliki bandwidth yang cukup untuk mengirim file manifest.
    - B. Karena permission dan icon native didefinisikan secara statis pada lapisan OS shell (`AndroidManifest.xml` / `Info.plist`) yang dikompilasi ke dalam native binary dan tidak dapat diubah oleh JavaScript runtime engine.
    - C. Karena Metro bundler secara otomatis menghapus konfigurasi XML.
    - D. Karena compiler Hermes hanya mengizinkan pengunduhan file JSON.

---

#### Bagian 3: Production Engineering Scenarios (Studi Kasus Nyata)

11. **Skenario Kasus 1**: Tim Anda merilis versi `v2.4.0` ke Google Play Store via track Production dengan Phased Rollout 10%. Dua jam pasca rilis, dashboard Sentry menangkap lonjakan *crash rate* menjadi 4.5% (ambang batas batas kritis SLA: 0.1%). Seluruh crash terisolir pada perangkat Samsung dengan Android 14. Apa langkah mitigasi automasi terstruktur pertama yang harus diambil oleh CI/CD engine atau release manager?
    - A. Menghapus aplikasi dari Google Play Store secara permanen.
    - B. Memanggil Google Play Developer API untuk melakukan *Halt Rollout* pada versi `v2.4.0` agar pengguna 90% lainnya tidak mengunduh build tersebut, sementara tim engineering menganalisis dSYM/R8 stack trace.
    - C. Mendorong OTA Update langsung ke seluruh pengguna secara serentak.
    - D. Menyiapkan rilis binary baru `v2.4.1` dan langsung menaikkan rollout ke 100% untuk menimpa crash.

12. **Skenario Kasus 2**: Anda mengonfigurasi Fastlane `match` untuk aplikasi iOS enterprise. Tiba-tiba seluruh pipeline CI gagal saat eksekusi `match(type: "appstore")` dengan pesan kesalahan: `Decryption failed: OpenSSL::Cipher::CipherError: bad decrypt`. Rekan satu tim Anda mengonfirmasi bahwa mereka baru saja memperbarui profil provisi dari laptop lokal mereka. Apa akar penyebab paling logis dari kegagalan pipeline ini?
    - A. Repository GitHub Actions sedang down.
    - B. Rekan tim tersebut mengubah password enkripsi `MATCH_PASSWORD` saat melakukan pembaruan profil di lokal, tanpa memperbarui secret `MATCH_PASSWORD` yang tersimpan pada CI/CD repository secrets.
    - C. Apple Developer Portal mencabut akun pengembang perusahaan.
    - D. Mac runner di cloud kehabisan disk space untuk mendekripsi sertifikat.

13. **Skenario Kasus 3**: Tim QA mendapati bahwa automation test black-box (Maestro/Detox) pada pipeline CI selalu gagal pada skenario login OTP, karena SMS gateway sandbox sering mengalami rate limit saat menerima request dari ratusan build test runner paralel. Sebagai Mobile Architect, solusi engineering deterministik mana yang paling tepat untuk diterapkan di lingkungan CI?
    - A. Mematikan skenario pengetesan login OTP dari pipeline CI/CD.
    - B. Mengimplementasikan conditional build config / *Hermes Mock Interceptor* khusus flavor/scheme `Staging/E2E` yang secara deterministik mengembalikan token OTP universal (misal `666666`) hanya jika aplikasi dikompilasi di bawah environment flag `IS_E2E_BUILD=true`.
    - C. Menambah waktu `sleep` pada skenario Maestro sebanyak 120 detik.
    - D. Mengubah provider SMS gateway setiap kali pipeline CI dijalankan.

---

### Kunci Jawaban & Evaluasi

#### Bagian 1: Basic Concept
1. **B** — Fastlane `match` adalah implementasi Git-based code signing identity yang deterministik menggunakan repo privat terenkripsi.
2. **C** — Google Play Dynamic Delivery mengurai `.aab` menjadi split APKs, secara signifikan memangkas ukuran biner akhir di perangkat user.
3. **B** — Mach-O dSYM (*Debug Symbol*) files memetakan memory addresses crash kembali ke baris kode asli Swift/Objective-C/C++.
4. **B** — OTA updates secara eksklusif beroperasi pada bundle JS dan dynamic asset, terpisah dari binary native shell.
5. **B** — Pre-kompilasi bytecode Hermes mengeliminasi proses parsing AST JS yang mahal di perangkat, menghasilkan TTI (*Time-To-Interactive*) yang instan.

#### Bagian 2: Intermediate Architectural
6. **B** — CocoaPods cache yang dikunci via checksum `Podfile.lock` menghindari download dan ekstraksi berulang ratusan library native pada ephemeral runner.
7. **C** — Runtime akan mencari native TurboModule implementation yang tidak ada pada native shell lama, menghasilkan unhandled native pointer dereference atau JS exception.
8. **B** — Mencegah *state poisoning* atau disparitas antara kode yang di-commit pada Git dengan artefak aktual yang diproduksi oleh runner.
9. **B** — App Store Connect API Key menggunakan JWT terstandarisasi yang dirancang khusus untuk integrasi mesin-ke-mesin tanpa dependensi sesi 2FA interaktif.
10. **B** — Perubahan native requirements memerlukan serialisasi ke binary OS dan pendaftaran oleh installer paket sistem operasi, yang mustahil dilakukan lewat eksekusi JS dinamis di runtime.

#### Bagian 3: Production Engineering Scenarios
11. **B** — Langkah pertama adalah menghentikan penyebaran kerusakan (*blast radius reduction*) melalui *Halt Rollout* via API sebelum menyusun strategi perbaikan.
12. **B** — `OpenSSL::Cipher::CipherError: bad decrypt` secara matematis mengindikasikan bahwa data di repo Git tidak dapat didekripsi menggunakan passphrase `MATCH_PASSWORD` yang aktif di CI environment.
13. **B** — Menggunakan mock environment deterministik pada target build non-production adalah pola standar industri untuk mengisolasi flakiness dependensi pihak ketiga pada pipeline validasi otomatis.

---

### 16. Summary

Implementasi CI/CD modern dan App Store Deployment berskala Enterprise pada React Native menuntut pemisahan domain yang presisi antara **Native Binary Toolchain** dan **Hermes Dynamic Layer**. Keandalan sistem rilis bergantung pada:
1. **Determinisme Infrastruktur**: Menghilangkan variasi lingkungan lokal menggunakan containerized/virtualized pipeline, dependency locking mutlak, dan sentralisasi sertifikat terenkripsi (`match`).
2. **Observabilitas Otomatis**: Integrasi tanpa putus antara proses build dengan sistem ingest *symbolication mapping* (dSYM, ProGuard) agar setiap crash di produksi langsung dapat diidentifikasi sumbernya.
3. **Pelepasan Terukur (Gradual Blast Radius)**: Menggunakan kombinasi *Phased Rollouts* di tingkat toko aplikasi dan *Semantic OTA Updates* untuk perbaikan darurat, yang didukung oleh guardrails otomatis untuk mitigasi crash secara real-time.