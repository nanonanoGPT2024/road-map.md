# BAB-10-CI-CD-Automated-Testing-dan-App-Store-Deployment: Quiz, Challenge, & Knowledge Check

Dokumen evaluasi mandiri ini dirancang untuk menguji pemahaman konseptual, arsitektur pipeline, otomatisasi rilis, serta mitigasi insiden produksi terkait CI/CD, Automated Testing, dan App Store Deployment pada ekosistem React Native.

---

## Bagian 1: Basic Questions (5 Soal)

### Soal 1: Perbedaan Mendasar Unit Testing, Integration Testing, dan E2E Testing
**Pertanyaan:**  
Jelaskan perbedaan mendasar antara Unit Testing (Jest), Integration Testing (React Native Testing Library - RNTL), dan End-to-End (E2E) Testing (Maestro / Detox) dalam konteks piramida testing React Native! Mengapa tidak semua alur aplikasi diuji menggunakan E2E testing?

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

* **Unit Testing (Jest):** Menguji unit terkecil kode secara terisolasi tanpa rendering UI native atau dependensi eksternal (contoh: pure functions, utility helpers, Redux reducers/selectors, custom hooks logic). Eksekusi sangat cepat (milidetik) dan murah secara komputasi.
* **Integration Testing (RNTL):** Menguji interaksi antar komponen React Native dan state management dalam environment virtual DOM/simulated tree (jsdom/react-test-renderer). Fokus pada verifikasi bahwa komponen merespons interaksi pengguna (tekan tombol, input teks) dan memicu side-effect yang diharapkan tanpa butuh emulator/simulator native.
* **End-to-End (E2E) Testing (Maestro / Detox):** Menguji aplikasi compiled biner nyata (`.apk` / `.aab` / `.ipa` atau `.app`) di dalam simulator/emulator atau real devices. Menguji full-stack integration dari UI native view, bridge/JSI runtime, bridging permissions, native modules, hingga koneksi real/mocked backend API.

**Alasan Mengapa Tidak Semua Alur Diuji Menggunakan E2E:**
1. **Execution Time & Flakiness:** E2E test membutuhkan build binary lengkap, booting simulator, dan rentan terhadap *flakiness* akibat timing animasi, cold-start latensi, dan asinkronitas OS native.
2. **Resource & Cost:** E2E test memakan resource CPU/RAM besar di CI runner (terutama macOS runner untuk iOS) yang jauh lebih mahal secara billing menit CI dibanding Linux runner.
3. **Debugging Complexity:** Root cause failure pada E2E test jauh lebih sulit diisolasi dibanding Unit/Integration test yang langsung menunjuk baris kode spesifik.
</details>

---

### Soal 2: Peran Fastlane Match vs Fastlane Sigh/Cert
**Pertanyaan:**  
Dalam continuous delivery iOS menggunakan Fastlane, apa keunggulan utama menggunakan `fastlane match` (metode *Codesigning Sync*) dibandingkan alur konvensional `cert` dan `sigh`? Jelaskan risiko keamanan yang harus diantisipasi saat mengelola private repository sertifikat!

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

* **Keunggulan `match` dibanding `cert`/`sigh`:**
  * `cert` dan `sigh` membuat sertifikat dan provisioning profile baru di Apple Developer Portal secara ad-hoc per developer machine. Hal ini cepat menghabiskan kuota sertifikat (maksimal limit per akun) dan memicu konflik sertifikat antar anggota tim dan CI runner.
  * `match` menerapkan konsep *Single Source of Truth*. Seluruh tim development dan CI runner berbagi 1 set Development/Distribution Certificate dan Provisioning Profile yang sama. Semua aset dienkripsi dengan OpenSSL AES-256 dan disimpan dalam private Git repository, Google Cloud Storage, atau AWS S3.
* **Risiko Keamanan & Mitigasi:**
  * **Repo Compromise:** Jika private repo bocor, penyerang membutuhkan passphrase (`MATCH_PASSWORD`) untuk mendekripsi file `.p12` dan profil. Passphrase harus disimpan di Secrets Manager/CI Secret dan memiliki rotasi berkala.
  * **Akses Developer Portal:** Penggunaan App Store Connect API Key (`.p8`) yang di-scope ke role *App Manager* atau *Developer* lebih aman dibanding Apple ID credentials dengan SMS 2FA.

</details>

---

### Soal 3: Semantic Versioning, `versionCode`, dan `CFBundleVersion`
**Pertanyaan:**  
Bagaimana korelasi antara SemVer (`version` di `package.json`, misal `2.4.1`) dengan konfigurasi native versioning pada Android (`versionCode` vs `versionName`) dan iOS (`CFBundleVersion` vs `CFBundleShortVersionString`)? Apa dampaknya jika `versionCode` atau `CFBundleVersion` tidak dinaikkan saat mengunggah build baru ke Google Play Console atau TestFlight?

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

* **Korelasi Versioning:**
  * **User-facing Version (SemVer):** Ditampilkan ke pengguna di App Store & Play Store.
    * Android: `versionName` (di `app/build.gradle`).
    * iOS: `CFBundleShortVersionString` (di `Info.plist`).
    * Nilai ini dipetakan dari semantic versioning (`MAJOR.MINOR.PATCH`).
  * **Machine/Build Counter:** Identifikasi unik untuk binary upload dalam satu rilis store.
    * Android: `versionCode` (integer monotonik meningkat, misal `1020401`).
    * iOS: `CFBundleVersion` / Build Number (integer atau dot-separated string, misal `42` atau `2.4.1.1`).
* **Dampak Jika Tidak Dinaikkan:**
  * **Google Play Console:** API upload (`upload_to_play_store` / `bundletool`) akan langsung menolak (`400 Bad Request: Version code X has already been used`). Play Store tidak mengizinkan penimpaan APK/AAB dengan `versionCode` yang sama atau lebih rendah.
  * **TestFlight / App Store Connect:** Binary processing akan memicu error `Redundant Binary Upload` atau `Invalid Bundle Build`. TestFlight mewajibkan setiap binary baru dalam `CFBundleShortVersionString` yang sama memiliki `CFBundleVersion` yang lebih tinggi secara strictly sequential.
</details>

---

### Soal 4: Keuntungan Android App Bundle (.aab) vs APK Standar
**Pertanyaan:**  
Mengapa Google Play Store mewajibkan format Android App Bundle (`.aab`) untuk aplikasi baru sejak 2021 dibanding Single Universal `.apk`? Bagaimana mekanisme Play Feature Delivery dan Dynamic Delivery bekerja mereduksi ukuran download user?

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

* **Alasan Wajib `.aab`:**
  * File `.aab` adalah format publishing yang berisi semua compiled code dan resource aplikasi, namun mendelegasikan proses pembuatan APK akhir dan penandatanganan rilis ke Google Play Store (menggunakan *Play App Signing*).
* **Mekanisme Dynamic Delivery:**
  * Google Play memecah bundle menjadi *Split APKs*. Ketika user mengunduh aplikasi, Google Play hanya mengirimkan:
    1. **Base APK:** Berisi kode inti aplikasi.
    2. **ABI Split APK:** Hanya arsitektur native CPU device target (contoh: `arm64-v8a` saja, tanpa menyertakan `armeabi-v7a` atau `x86_64`).
    3. **Screen Density Split APK:** Hanya aset resolusi yang sesuai dengan layar perangkat user (misal `xxhdpi` saja, tanpa `mdpi` atau `ldpi`).
    4. **Language Split APK:** Hanya string bahasa sesuai locale pengguna.
  * Hasilnya, ukuran unduhan (download size) dan storage footprint di perangkat pengguna terpangkas 20% hingga 50% dibanding universal APK.
</details>

---

### Soal 5: Cache Strategy pada Runner CI (GitHub Actions)
**Pertanyaan:**  
Sebutkan tiga jenis cache direktori krusial yang wajib dikonfigurasi dalam pipeline GitHub Actions untuk React Native (Android & iOS) agar waktu eksekusi build tidak memakan waktu puluhan menit di setiap run!

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

1. **Dependency Manager Cache (Node Modules):**
   * Path: `~/.npm` (NPM), `~/.cache/yarn` (Yarn), atau `~/.local/share/pnpm/store` (PNPM). Dikelola menggunakan action `actions/setup-node` dengan parameter `cache: 'yarn'` atau cache key berbasis lockfile hash (`yarn.lock` / `pnpm-lock.yaml`).
2. **Gradle Cache (Android):**
   * Path: `~/.gradle/caches`, `~/.gradle/wrapper`. Menyimpan downloaded dependency JAR/AAR dari Maven Central/Google, serta compiler daemon artifacts. Dikelola via `gradle/actions/setup-gradle` atau `actions/cache`.
3. **Cocoapods & Ruby Gems Cache (iOS - macOS Runner):**
   * Path: `ios/Pods` (opsional jika Pods di-commit/dikelola cermat), CocoaPods spec cache `~/.cocoapods`, dan Ruby bundler cache `vendor/bundle`. Menghemat waktu downloading spec repositori dan instalasi gem Fastlane.
</details>

---

## Bagian 2: Intermediate Questions (5 Soal)

### Soal 6: Mocking Native Modules dan JSI pada Jest
**Pertanyaan:**  
Sebuah komponen memanfaatkan library native modern seperti `@react-native-async-storage/async-storage` dan `react-native-reanimated`. Ketika dijalankan di Jest, muncul pesan error:  
`TypeError: Cannot read property 'install' of undefined` atau `Reanimated 2/3 failed to create a worklet`.  
Bagaimana arsitektur mock Jest mengatasi ketiadaan native runtime C++/JSI di Node.js, dan bagaimana struktur setup file yang benar?

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

* **Akar Masalah:** Jest berjalan di lingkungan runtime V8/Node.js murni tanpa JavaScript Engine khusus perangkat (Hermes Native Bridge / JSI Host Objects) dan tanpa Cocoa/Android OS runtime. Pemanggilan C++ JSI bindings langsung akan menghasilkan `undefined` karena binding native tidak pernah di-load di Node.js.
* **Solusi Arsitektural:** Melakukan mocking pada layer JS library sebelum mencapai native JSI layer.
* **Implementasi Setup (`jest.setup.js`):**
  ```javascript
  // Mock AsyncStorage
  import mockAsyncStorage from '@react-native-async-storage/async-storage/jest/async-storage-mock';
  jest.mock('@react-native-async-storage/async-storage', () => mockAsyncStorage);

  // Mock Reanimated
  require('react-native-reanimated').setUpTests();

  // Mock NativeAnimatedHelper untuk menghindari warning act()
  jest.mock('react-native/Libraries/Animated/NativeAnimatedHelper');
  ```
  File ini didaftarkan di `jest.config.js` pada properti `setupFilesAfterEnv: ['<rootDir>/jest.setup.js']`.
</details>

---

### Soal 7: Fastlane Lane Composition & Nonce/2FA Handling
**Pertanyaan:**  
Mengapa penggunaan email dan password akun Apple ID reguler sangat tidak disarankan untuk pipeline CI/CD di Fastlane? Jelaskan bagaimana implementasi App Store Connect API Key (`key_id`, `issuer_id`, `key_filepath`) memecahkan masalah session expiry dan Two-Factor Authentication (2FA) di environment headless CI!

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

* **Kelemahan Apple ID dengan 2FA di CI:**
  * Apple memberlakukan mandatory 2FA untuk semua Apple ID. Di server CI tanpa antarmuka interaktif, prompt SMS atau six-digit verification code menyebabkan pipeline hang dan timeout.
  * Solusi legacy `FASTLANE_SESSION` (menggunakan session cookies) hanya bertahan maksimal 30 hari, sehingga pipeline sewaktu-waktu tiba-tiba putus di tengah malam saat cookie kadaluarsa.
* **Keunggulan App Store Connect API Key:**
  * Menggunakan standar token JSON Web Token (JWT) yang di-sign menggunakan private key `.p8`.
  * Sepenuhnya *machine-to-machine*, tidak memerlukan interaksi login manusia, tidak kedaluwarsa secara berkala (kecuali revoked di portal), dan kebal terhadap protokol 2FA browser.
  * Di Fastlane, dikonfigurasi melalui action:
    ```ruby
    app_store_connect_api_key(
      key_id: ENV["ASC_KEY_ID"],
      issuer_id: ENV["ASC_ISSUER_ID"],
      key_content: ENV["ASC_KEY_P8_BASE64"], # Di-inject via CI secret
      is_key_content_base64: true,
      in_house: false
    )
    ```
</details>

---

### Soal 8: Dynamic Keystore & Secrets Handling di Android Pipeline
**Pertanyaan:**  
Dalam continuous integration yang aman, file `release.keystore` tidak boleh di-commit ke Git. Jelaskan pola standar untuk mendekodekan keystore berbasis Base64 string dari environment variables ke filesystem runner secara aman di Gradle, serta bagaimana menjaga password keystore agar tidak terekspos di log runner!

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

* **Pola Pengkodean dan Penanganan File:**
  1. Encode binary keystore ke Base64 lokal: `base64 -w 0 release.keystore > keystore.base64`.
  2. Simpan string Base64 ke Secret Provider (GitHub Actions Secrets: `ANDROID_KEYSTORE_BASE64`).
  3. Pada step CI runner sebelum build Gradle, decode kembali ke path sementara yang aman:
     ```bash
     echo "$ANDROID_KEYSTORE_BASE64" | base64 --decode > android/app/release.keystore
     ```
  4. Hapus file biner setelah build selesai pada step `always()` post-action.
* **Proteksi Log & Konfigurasi Gradle:**
  * Hindari hardcode password di `app/build.gradle`. Gunakan Gradle Project Properties atau Environment Variables:
    ```groovy
    signingConfigs {
        release {
            storeFile file(System.getenv("KEYSTORE_PATH") ?: "release.keystore")
            storePassword System.getenv("KEYSTORE_PASSWORD")
            keyAlias System.getenv("KEY_ALIAS")
            keyPassword System.getenv("KEY_PASSWORD")
        }
    }
    ```
  * Runner GitHub Actions secara otomatis menyamarkan (`***`) nilai yang dideklarasikan di `secrets.*`. Namun, developer harus memastikan flags Gradle tidak menggunakan `--info` atau `--debug` yang berisiko men-dump argumen JVM ke stdout.
</details>

---

### Soal 9: Proguard/R8 Minification & Upload Mapping ke Crashlytics
**Pertanyaan:**  
Ketika mengaktifkan `enableProguardInReleaseBuilds = true` di Android, aplikasi mengalami crash saat rilis produksi. Stacktrace di Sentry atau Firebase Crashlytics hanya berisi simbol acak (misal: `a.b.c.v(): unknown source`). Jelaskan apa yang terjadi, apa fungsi file `mapping.txt`, dan bagaimana mengotomatisasi upload deobfuscation mapping pada pipeline Fastlane/Gradle!

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

* **Akar Masalah:** R8/Proguard melakukan *shrinking*, *optimization*, dan *obfuscation* untuk memperkecil ukuran biner dan mempersulit reverse engineering. Class, method, dan variabel diganti menjadi nama pendek 1-2 huruf (`a`, `b.c`).
* **Fungsi `mapping.txt`:** File tabel terjemahan dua arah yang memetakan nama asli kode sumber ke simbol yang di-obfuscate. Tanpa file ini, stacktrace crash tidak bisa dibaca (*de-obfuscated*).
* **Otomatisasi Pipeline:**
  * Untuk **Firebase Crashlytics**: Tambahkan plugin Crashlytics Gradle (`com.google.firebase.crashlytics`) di `app/build.gradle`. Task `assembleRelease` atau `bundleRelease` akan otomatis mengunggah file mapping jika Google Services JSON tersedia.
  * Untuk **Sentry via Fastlane**:
    ```ruby
    lane :upload_android_symbols do
      sentry_upload_dif(
        auth_token: ENV["SENTRY_AUTH_TOKEN"],
        org_slug: 'my-org',
        project_slug: 'react-native-app',
        path: 'android/app/build/outputs/mapping/release/mapping.txt'
      )
    end
    ```
  * Aset mapping juga wajib diarsipkan sebagai CI build artifact (`actions/upload-artifact`) untuk keperluan audit forensik.
</details>

---

### Soal 10: Deteksi Flaky Test pada Test Runner E2E
**Pertanyaan:**  
Apa perbedaan mekanisme sinkronisasi state antara **Detox** (*Grey Box Testing*) dan **Maestro** (*Black Box Declarative Testing*)? Mengapa Detox lebih rentan mengalami dead-lock pada aplikasi React Native yang memiliki infinite background loop (misal: periodic polling atau looping animation)?

<details>
<summary><b>Kunci Jawaban & Pembahasan</b></summary>

* **Mekanisme Detox (Grey Box):**
  * Detox menyuntikkan kode native monitor (*EarlGrey* di iOS dan *Espresso* di Android) ke dalam thread proses aplikasi.
  * Detox secara otomatis menunggu aplikasi mencapai kondisi *idle* (semua queue kosong: JavaScript Event Loop, UI thread, network request, dan Animasi Native) sebelum mengeksekusi step berikutnya.
  * **Penyebab Dead-lock:** Jika terdapat timer berulang (`setInterval`), looping SVG/Lottie animation tanpa stop, atau continuous background polling, Detox menganggap aplikasi tidak pernah idle. Akibatnya, test macet (*hang*) dan timeout. Solusinya membutuhkan konfigurasi `launchArgs` atau mock idle synchronizer.
* **Mekanisme Maestro (Black Box):**
  * Maestro berjalan sepenuhnya di luar proses aplikasi via OS Accessibility Framework (UIAutomator di Android, XCUITest accessibility di iOS).
  * Maestro tidak memantau internal thread queues, melainkan menggunakan model deklaratif: menunggu elemen muncul di accessibility hierarchy (`assertVisible`, `extendedWaitUntil`). Maestro tidak terpengaruh oleh background loop JS internal sehingga jauh lebih tahan flakiness untuk use-case visual dan end-to-end integration.
</details>

---

## Bagian 3: Skenario Kasus Nyata Produksi (3 Kasus)

### Kasus 1: Insiden "Stale JS Bundle" Pasca-Release OTA
**Skenario:**  
Tim merilis hotfix v3.1.1 menggunakan OTA (Over-The-Air Update) CodePush/Expo Updates. Namun, 40% user yang melakukan update melaporkan aplikasi crash instan saat splash screen (*White Screen of Death*). Tim QA menemukan bahwa crash terjadi karena kode JavaScript memanggil native method baru dari modul kamera yang baru saja di-merge ke branch main.

1. **Analisis Penyebab:** Mengapa update OTA tersebut berakibat fatal?
2. **Immediate Remediation:** Langkah apa yang harus diambil secara darurat?
3. **CI/CD Prevention:** Kebijakan validasi otomatis apa yang wajib dipasang di pipeline CI agar rilis OTA tidak pernah merusak kompatibilitas native?

<details>
<summary><b>Analisis & Solusi Kasus 1</b></summary>

* **1. Analisis Penyebab:**
  * Pelanggaran aturan fundamental OTA: **OTA hanya boleh berisi perubahan aset JavaScript dan gambar**, tidak boleh ada penambahan, penghapusan, atau perubahan signature method C++/Java/Objective-C Native Modules.
  * User di v3.1.0 memiliki biner native lama yang belum memiliki modul native baru. Ketika JS Bundle baru di-load, pemanggilan `NativeModules.NewCameraModule` menghasilkan `null/undefined`, memicu unhandled runtime error saat inisialisasi aplikasi.
* **2. Immediate Remediation:**
  * Segera lakukan **Rollback OTA Target** di dashboard CodePush/Expo Updates ke release rilis stabil sebelumnya, atau set status release tersebut menjadi `disabled`/`targetBinaryVersion` dibatasi ke versi biner baru saja.
* **3. CI/CD Prevention:**
  * **Target Binary Version Strict Pinning:** Pastikan perintah publikasi OTA mengunci target binary version secara eksplisit (contoh: `--target-binary-version 3.1.1` dan bukan wildcard `*`).
  * **Automated Native Diff Guard:** Buat custom script di pipeline CI yang membandingkan `android/` dan `ios/` folder serta `package.json` antara commit rilis dengan tag rilis produksi terakhir. Jika terdeteksi perubahan pada file native atau penambahan native library, pipeline OTA otomatis **abort** dan mewajibkan full App Store / Play Store binary release.
</details>

---

### Kasus 2: iOS Build Rejection "Missing ITMS-90683: Missing Purpose String"
**Skenario:**  
Pipeline Fastlane berhasil mengunggah `.ipa` ke App Store Connect. Namun 10 menit kemudian, status build di TestFlight berubah menjadi *Processing Failed* dan pengelola rilis menerima email otomatis dari Apple:
> *ITMS-90683: Missing Purpose String in Info.plist. Your app's code references one or more APIs that access sensitive user data... NSBluetoothAlwaysUsageDescription.*

Developer bersumpah mereka tidak pernah menambahkan fitur Bluetooth.

1. **Investigasi:** Dari mana dependensi API Bluetooth tersebut berasal?
2. **Mitigasi Teknis:** Bagaimana cara mengidentifikasi library pihak ketiga yang membawa simbol native Bluetooth tersebut?
3. **Penyelesaian:** Bagaimana langkah preventif di pipeline Fastlane/CI sebelum biner di-upload ke Apple?

<details>
<summary><b>Analisis & Solusi Kasus 2</b></summary>

* **1. Akar Masalah:**
  * Library pihak ketiga (sering kali SDK analitik, periklanan, atau tracking seperti Facebook SDK, Segment, atau library periferal) memuat kode native yang mengimpor `CoreBluetooth.framework`.
  * Sistem static analysis Apple memindai seluruh simbol biner biner `.ipa`. Jika simbol API Bluetooth terdeteksi, Apple mewajibkan deskripsi privasi di `Info.plist`, terlepas dari apakah fitur tersebut dipanggil secara aktif saat runtime atau tidak.
* **2. Cara Investigasi:**
  * Periksa symbols di compiled framework menggunakan utility `nm` atau `otool` di runner macOS:
    ```bash
    nm -u ios/build/Build/Products/Release-iphoneos/YourApp.app/YourApp | grep -i CBCentralManager
    ```
  * Periksa `Podfile.lock` untuk meninjau dependensi transitive yang menarik CoreBluetooth.
* **3. Penyelesaian & Pencegahan:**
  * Tambahkan key `NSBluetoothAlwaysUsageDescription` dengan penjelasan kontekstual di `Info.plist`, ATAU gunakan sub-spec modular dari library tersebut (contoh: pada library analitik, pilih varian tanpa native sensor/ad tracking).
  * Pasang **Pre-flight Plist Linter** di Fastlane sebelum step `upload_to_testflight`:
    ```ruby
    lane :verify_privacy_strings do
      plist = read_plist(path: "ios/YourApp/Info.plist")
      required_keys = ["NSCameraUsageDescription", "NSBluetoothAlwaysUsageDescription"]
      # Skrip verifikasi kelengkapan key
    end
    ```
</details>

---

### Kasus 3: OOM Crash pada GitHub Actions Hosted Runner saat Build Android
**Skenario:**  
Pipeline Android di GitHub Actions (menggunakan runner `ubuntu-latest` dengan 7 GB RAM) sering gagal secara acak saat menjalankan step `./gradlew bundleRelease`. Error log menunjukkan:
> *Expiring Daemon because JVM heap space is exhausted*  
> *Process 'Gradle Worker 2' finished with non-zero exit value 137 (SIGKILL).*

1. **Root Cause Analysis:** Apa yang menyebabkan JVM kehabisan memori dan terbunuh oleh OS?
2. **JVM & Gradle Tuning:** Nilai konfigurasi apa yang harus disesuaikan di `gradle.properties`?
3. **Resource Isolation:** Bagaimana konfigurasi optimal agar compiler Hermes, R8, dan Gradle daemon dapat berbagi RAM secara aman di runner dengan RAM terbatas?

<details>
<summary><b>Analisis & Solusi Kasus 3</b></summary>

* **1. Root Cause Analysis:**
  * Exit code `137` menandakan proses dihentikan secara paksa oleh **Linux Out-Of-Memory (OOM) Killer**.
  * Gradle secara default menjalankan multiple worker concurrent (`org.gradle.parallel=true`) dan mengalokasikan heap memory JVM yang bertabrakan dengan konsumsi memori saat kompilasi C++ Hermes dan optimasi R8 Proguard. Total penggunaan memori melampaui limit 7 GB runner.
* **2. Tuning `gradle.properties` untuk CI:**
  ```properties
  # Batasi heap memory JVM Gradle Daemon agar menyisakan ruang untuk Node/Hermes
  org.gradle.jvmargs=-Xmx3072m -XX:MaxMetaspaceSize=512m -XX:+HeapDumpOnOutOfMemoryError

  # Matikan daemon persistent di lingkungan ephemeral CI (menghemat overhead)
  org.gradle.daemon=false

  # Batasi concurrent worker agar tidak spawn compiler berlebihan
  org.gradle.workers.max=2

  # Cache & parallel build configuration
  org.gradle.parallel=false
  android.enableR8.fullMode=false
  ```
* **3. Node / Metro Memory Limitation:**
  Set environment variable Node pada step CI:
  ```bash
  export NODE_OPTIONS="--max-old-space-size=2048"
  ```
  Ini menjamin Node.js (Metro bundler) mengonsumsi maksimal 2 GB, JVM Gradle maksimal 3 GB, sehingga total 5 GB tetap berada di bawah ambang batas bahaya 7 GB RAM runner.
</details>

---

## Bagian 4: Practical Chapter Challenge

### Judul Tantangan:
**Membangun Production-Grade Dual-Platform CI/CD Pipeline dengan GitHub Actions, Fastlane, dan Automated Quality Gate.**

### Deskripsi Masalah:
Anda adalah Staff Mobile Platform Engineer di perusahaan fintech. Tim mobile membutuhkan pipeline otomatisasi lengkap pada repositori React Native mereka. Pipeline harus mampu memverifikasi kualitas kode pada setiap Pull Request, serta membangun dan merilis binary staging secara otomatis ke Google Play Internal App Sharing dan Apple TestFlight ketika ada tag baru yang di-push.

### Tugas yang Harus Diselesaikan:

1. **Konfigurasi Quality Gate Pipeline (`.github/workflows/quality-gate.yml`):**
   * Trigger: Pull Request ke branch `main` dan `staging`.
   * Steps:
     * Checkout kode dan setup Node environment dengan caching PNPM/Yarn.
     * Linting: ESLint dan Prettier check.
     * Type-check: `tsc --noEmit`.
     * Unit & Component Test: Eksekusi Jest dengan flag `--coverage` dan batasan threshold minimum 75% coverage.
     * Report: Upload coverage report sebagai artifact.

2. **Konfigurasi Fastlane iOS (`ios/fastlane/Fastfile`):**
   * Buat lane `:beta` yang:
     * Mengambil kredensial App Store Connect via API Key `.p8`.
     * Menjalankan `match(type: "appstore", readonly: true)`.
     * Menginkremen build number secara otomatis (`increment_build_number`).
     * Membangun `.ipa` release (`build_app`).
     * Mengunggah build ke TestFlight tanpa menunggu status processing selesai (`skip_waiting_for_build_processing: true`).

3. **Konfigurasi Fastlane Android (`android/fastlane/Fastfile`):**
   * Buat lane `:beta` yang:
     * Mendekodekan release keystore dari environment variable base64.
     * Menjalankan `./gradlew bundleRelease`.
     * Mengunggah `.aab` ke Google Play Store track `internal` menggunakan Google Play Android Developer API service account json.
     * Membersihkan file `.keystore` sementara setelah rilis selesai.

4. **Konfigurasi Release Pipeline (`.github/workflows/release.yml`):**
   * Trigger: Tag rilis berformat `v*.*.*` (contoh: `v1.2.0`).
   * Menggunakan 2 parallel jobs: `build-android` (di runner `ubuntu-latest`) dan `build-ios` (di runner `macos-14`).
   * Menjalankan Fastlane lane yang bersangkutan dengan proteksi secrets yang lengkap.

### Kriteria Kelulusan (Acceptance Criteria):
* [ ] Seluruh workflow GitHub Actions menggunakan dynamic secret referencing (`${{ secrets.* }}`), tanpa ada hardcoded token.
* [ ] Caching dikonfigurasi dengan benar untuk Yarn/NPM, Gradle (`~/.gradle`), dan CocoaPods.
* [ ] Job Android berhasil menghasilkan artifact `.aab` yang signed dan terverifikasi.
* [ ] Job iOS berhasil melakukan code-signing tanpa interaktivitas prompt 2FA.
* [ ] Skrip membersihkan file keystore/sertifikat sensitif saat job selesai atau gagal.

---

## Bagian 5: Checklist Pemahaman Mandiri

Gunakan daftar centang ini untuk memvalidasi kesiapan Anda dalam mengelola alur rilis aplikasi React Native berskala enterprise:

- [ ] **Testing Pyramid:** Memahami kapan harus menulis Unit Test (Jest), Integration Test (RNTL), dan E2E Test (Maestro/Detox).
- [ ] **Automated Mocking:** Mampu mengisolasi Native Modules, Reanimated, dan Navigation di level test runner.
- [ ] **Android App Signing:** Menguasai pembuatan upload keystore, Play App Signing, dan encoding aman berbasis Base64 di CI.
- [ ] **Apple Code Signing:** Memahami relasi Certificate, App ID, Entitlements, dan Provisioning Profile, serta implementasi `fastlane match`.
- [ ] **Modern Store Automation:** Mampu mengonfigurasi App Store Connect API Key (`.p8`) dan Google Service Account JSON untuk akses headless.
- [ ] **Resource Optimization:** Mampu mengoptimasi Gradle memory (`jvmargs`, worker isolation) agar pipeline stabil di container dengan resource terbatas.
- [ ] **OTA Safety:** Memahami batasan kompatibilitas runtime JS Bundle terhadap Native Binary Bridge saat mendistribusikan hotfix.
- [ ] **Artifact & Deobfuscation:** Memastikan dSYM iOS dan R8/Proguard `mapping.txt` terunggah otomatis ke Sentry/Crashlytics di setiap build produksi.
