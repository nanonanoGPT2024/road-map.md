# Bab 10 Module 01: CI/CD, Automated Testing & App Store Deployment

---

## SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum**: `03-Frontend-and-Mobile`
*   **Spesialisasi**: React Native Enterprise Engineering
*   **Modul**: Bab 10, Modul 01
*   **Topik**: CI/CD, Automated Testing & App Store Deployment
*   **Prasyarat Konseptual**:
    *   Arsitektur React Native (Metro Bundler, JSI, Native Modules).
    *   Pengelolaan dependensi iOS (`CocoaPods`, `Podfile`, Xcode Workspace) dan Android (`Gradle`, `build.gradle`, Android SDK).
    *   Dasar pengujian JavaScript/TypeScript (`Jest`, Mocking).
    *   Pengendalian versi git (*Trunk-Based Development*, *Semantic Versioning*).
*   **Target Audiens**: Senior Mobile Engineers, Lead App Developers, DevSecOps Engineers, dan Staff Software Engineers yang mengelola siklus rilis multi-platform ke Apple App Store dan Google Play Store.

---

## SEKSI 02 — LEARNING OBJECTIVES

Pada akhir modul ini, peserta didik memiliki kapabilitas terukur untuk:
1.  **Membangun Pipeline CI/CD Komprehensif**: Mengonfigurasi alur kerja GitHub Actions multi-runner (Ubuntu dan macOS) untuk *linting*, *type checking*, pengujian otomatis, kompilasi biner native, dan distribusi.
2.  **Mengimplementasikan Strategi Testing Piramida Penuh**: Menyusun *Unit Tests* (Jest), *Integration/Component Tests* (React Native Testing Library), dan *End-to-End Tests* (Maestro/Detox) dengan strategi mock native yang deterministik.
3.  **Mengotomatisasi Orchestrasi Rilis dengan Fastlane**: Menulis *Fastfile* terstruktur untuk menangani *code signing* iOS (*Fastlane Match* via Git + OpenSSL), manajemen keystore Android, incrementing nomor versi biner, serta integrasi TestFlight dan Play Console Internal Track.
4.  **Mengamankan Jalur Suplai Software (Supply Chain Security)**: Menerapkan rotasi rahasia (*secrets management*), perlindungan sertifikat penandatanganan native, dan penegakan *reproducible builds*.
5.  **Menerapkan Pola Zero-Downtime Deployment**: Mengatur arsitektur rilis bertahap (*staged rollouts*), *canary deployments*, dan pemantauan telemetri regresi rilis menggunakan *crash reporting*.

---

## SEKSI 03 — MINDSET & MENTAL MODEL

Dalam ekosistem *web development*, kegagalan rilis dapat dimitigasi dalam hitungan detik melalui *instant rollback* atau injeksi kode langsung pada server origin. Pada ekosistem native mobile (React Native), rilis bersifat **asinkron, probabilistik, dan tertunda**:

```
[Web Mindset]    : Commit -> Build -> Push ke CDN -> 100% Pengguna menerima instan (<2 Menit)
[Mobile Mindset] : Commit -> Build Native -> App Review (2-48 Jam) -> Staged Rollout -> Ekosistem Terfragmentasi
```

### Prinsip Inti Rekayasa Rilis Mobile:
1.  **Biner Adalah Artefak Abadi**: Sekali sebuah `.ipa` atau `.aab` terdistribusi ke perangkat klien, versi tersebut akan tetap hidup di alam liar selama berbulan-bulan bahkan bertahun-tahun. Bug native kritis tidak bisa di-hotfix secara instan tanpa proses *review* toko aplikasi, kecuali menggunakan arsitektur OTA (*Over-The-Air*) yang memiliki batasan fungsionalitas native.
2.  **Determinisme Native vs Non-Determinisme Lingkungan**: React Native bergantung pada kompilasi C++, Objective-C/Swift, Java/Kotlin, dan bundel JavaScript. Pipeline CI/CD harus menjamin bahwa variasi versi NDK, Xcode Command Line Tools, dan CocoaPods menghasilkan output bit-per-bit yang identik di setiap mesin kompilasi.
3.  **Matriks Kegagalan Asinkron**: Pengujian otomatis pada React Native harus memperhitungkan jembatan komunikasi native (*bridge* atau JSI). Pengujian E2E tidak sekadar memverifikasi DOM virtual, melainkan menguji interaksi subsistem OS (aksesibilitas, thread rendering UI, thread background JavaScript, dan network layer native).

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Di bawah ini adalah topologi alur kerja terotomatisasi dari *pull request* developer hingga publikasi rilis biner ke Apple TestFlight dan Google Play Internal Track.

```
+---------------------------------------------------------------------------------------------------+
|                                  FASE 1: CONTINUOUS INTEGRATION (CI)                              |
+---------------------------------------------------------------------------------------------------+
  [Developer Git Push]
           │
           ▼
  ┌────────────────────────────────────────────────────────┐
  │                 GitHub Actions Runner                  │
  │                   (ubuntu-latest)                      │
  ├────────────────────────────────────────────────────────┤
  │ 1. Checkout Code + Node Setup (LTS)                    │
  │ 2. Install Deps (npm ci / yarn --frozen-lockfile)      │
  │ 3. Static Analysis: ESLint + TypeScript TypeCheck (tsc)│
  │ 4. Unit Testing: Jest (Mock Native Modules/TurboMods)  │
  │ 5. Component Integration: React Native Testing Library │
  └───────────────────────────┬────────────────────────────┘
                              │
                              ▼ (Pass)
+---------------------------------------------------------------------------------------------------+
|                              FASE 2: PARALLEL NATIVE MATRIX BUILDS                                |
+---------------------------------------------------------------------------------------------------+
              ┌───────────────┴────────────────┐
              │                                │
              ▼                                ▼
  ┌──────────────────────────────┐ ┌─────────────────────────────────────────┐
  │     ANDROID RUNNER           │ │              IOS RUNNER                 │
  │    (ubuntu-latest)           │ │            (macos-14 M1/M2)             │
  ├──────────────────────────────┤ ├─────────────────────────────────────────┤
  │ • Setup Java JDK 17 & NDK    │ │ • Select Xcode 15.x / 16.x              │
  │ • Restore Gradle Cache       │ │ • Restore CocoaPods & DerivedData Cache │
  │ • Fastlane Match / Keystore  │ │ • Fastlane Match (Decrypt Apple Certs)  │
  │ • Run Maestro E2E Headless   │ │ • Run Maestro iOS Simulator Test        │
  │ • ./gradlew bundleRelease    │ │ • Gym: Build & Archive .ipa             │
  │ • Output: release.aab        │ │ • Output: release.ipa                   │
  └──────────────┬───────────────┘ └────────────────────┬────────────────────┘
                 │                                      │
                 └──────────────────┬───────────────────┘
                                    │
                                    ▼
+---------------------------------------------------------------------------------------------------+
|                             FASE 3: CONTINUOUS DEPLOYMENT (FASTLANE)                              |
+---------------------------------------------------------------------------------------------------+
  ┌─────────────────────────────────────────────────────────────────────────────────┐
  │ Google Play Console API                        Apple App Store Connect API      │
  │ (Service Account JSON)                         (App Store Connect API Key p8)   │
  ├────────────────────────────────────────────────┼────────────────────────────────┤
  │ upload_to_play_store(                          │ upload_to_testflight(          │
  │   track: 'internal',                           │   skip_waiting_for_build_proc: │
  │   aab: 'release.aab'                           │     false,                         │
  │ )                                              │   ipa: 'release.ipa'           │
  │                                                │ )                              │
  └────────────────────────┬───────────────────────┴────────────────┬───────────────┘
                           │                                        │
                           ▼                                        ▼
                   [Play Internal Testers]                 [TestFlight Beta Team]
                           │                                        │
                           └───────────────────┬────────────────────┘
                                               │
                                               ▼
                              [Production Staged Rollout (10% -> 100%)]
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Dynamic Linking & Code Signing iOS
Apple menerapkan model keamanan biner berbasis tanda tangan digital kriptografis (*Signature Validation*):
*   **Certificate**: Pasangan kunci publik-privat (*X.509 standard*) yang dikeluarkan oleh Apple Developer Relations CA. Mengidentifikasi siapa pembuat biner (Developer vs Distribution).
*   **App ID & Entitlements**: Daftar kapabilitas native yang diizinkan (Apple Pay, Push Notifications, Keychain Sharing) yang ditandatangani secara kriptografis ke dalam biner.
*   **Provisioning Profile (`.mobileprovision`)**: Berkas penghubung yang berisi:
    1. Sertifikat Distribusi yang valid.
    2. Daftar UDID perangkat target (khusus mode Ad-Hoc/Development, tidak ada pada Distribution App Store).
    3. Entitlements yang disetujui Apple.
*   **Mekanisme Transaksi Fastlane Match**: Fastlane mengabstraksi kompleksitas ini dengan menyimpan sertifikat distribusi dan private key terenkripsi (*OpenSSL AES-256-CBC*) di repositori privat Git terpisah. Ketika CI berjalan, runner melakukan kloning repo sertifikat, mendekripsinya dengan `MATCH_PASSWORD`, dan menginstalnya langsung ke dalam *macOS Keychain* ephemeral runner.

### 2. Android Keystore, V1, V2, V3, and V4 Signing Schemes
Android biner ditandatangani menggunakan format berkas PKCS#12 atau Java Keystore (`.keystore`/`.jks`):
*   **V1 Signing (JAR Signature)**: Memverifikasi integritas berkas `.zip` per-entri. Mudah dimanipulasi melalui modifikasi metadata zip tanpa merusak hash entri.
*   **V2 Signing (Full APK Signature)**: Menambahkan blok tanda tangan biner khusus di antara data ZIP dan Central Directory. Melindungi seluruh integritas berkas biner secara kriptografis.
*   **V3 Signing**: Mendukung rotasi kunci (*key rotation history*) dalam blok tanda tangan native.
*   **Android App Bundle (AAB) & Play Feature Delivery**: Dalam pipeline CI modern, biner dikompilasi menjadi format `.aab` menggunakan *Android Asset Packaging Tool 2 (AAPT2)*. Pengembang menandatangani AAB menggunakan *Upload Key*. Google Play Infrastructure mengekstrak AAB, mengoptimalkan resource per konfigurasi perangkat target (densitas layar, ABI CPU: `arm64-v8a`, `armeabi-v7a`, `x86_64`), dan menandatangani ulang APK akhir dengan *App Signing Key* utama yang dikelola secara aman via *Google Cloud KMS*.

### 3. Pipeline Bundling React Native di Lingkungan CI
Ketika perintah build dijalankan (`./gradlew bundleRelease` atau `xcodebuild archive`):
1.  **Eksekusi Script Phase**: Gradle/Xcode memanggil Node.js runtime untuk mengeksekusi Metro Bundler CLI.
2.  **Transpilasi & Resolusi Modul**: Metro memetakan dependensi dari root `index.js`, mengubah TypeScript/ESNext menjadi bytecode JavaScript kompatibel via Babel/Hermes compiler.
3.  **Hermes Bytecode Compilation**: Metro menghasilkan JavaScript murni, yang kemudian segera diubah oleh kompilator `hermesc` native menjadi *Hermes Bytecode* (`index.android.bundle` / `main.jsbundle`). Hal ini menghasilkan file biner teroptimasi yang dimuat secara instan melalui *Memory Mapping* (`mmap`) saat aplikasi di-booting, melewati tahap evaluasi teks JavaScript runtime.
4.  **Asset Linking**: Aset grafis di-resolusi dan disalin ke subfolder platform spesifik (`android/app/src/main/res/drawable-*` dan `Assets.car` di iOS).

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Deterministik Pipeline & Manajemen State Dependency
Masalah paling sering dalam pipeline mobile adalah insiden "*It compiles on my local machine, but fails on CI*". Hal ini terjadi akibat ketidakcocokan dependensi native tiga-lapis:
1.  **Lapis JavaScript**: Node.js engine, `yarn.lock` atau `package-lock.json`.
2.  **Lapis iOS**: CocoaPods engine, Podfile.lock, Xcode command-line tools version, Ruby gems (`Gemfile.lock`).
3.  **Lapis Android**: Gradle wrapper (`gradle-wrapper.properties`), Gradle dependencies, Android SDK build-tools, NDK rilis spesifik, dan Java JDK version.

Untuk menjamin determinisme:
*   Kunci seluruh runtime platform menggunakan *tool version managers* seperti `.node-version`, `.ruby-version`, dan skrip wrapper (`./gradlew`).
*   Jalankan penginstalan dependensi murni non-interaktif: `npm ci` atau `yarn --immutable --immutable-cache`.
*   Jalankan `pod install --immutable` (pada versi CocoaPods modern) atau pastikan `Podfile.lock` diverifikasi ketat melalui checksum.

### Desain Piramida Pengujian React Native Skala Besar

```
             / \
            /   \
           / E2E \         Detox / Maestro (Runs on Native Simulators/Emulators)
          /-------\
         /  Integ  \       RNTL (React Native Testing Library - Component Tree & Hooks)
        /-----------\
       /  Unit Test  \     Jest (Pure Functions, Reducers, State Stores, Utilities)
      /---------------\
```

1.  **Unit Tests (Jest)**: Fokus pada logika bisnis murni tanpa rendering native. Eksekusi sangat cepat (~1-5 ms per test). Semua native bridge/JSI harus di-mocking secara statis.
2.  **Component & Integration Tests (RNTL)**: Merender virtual component tree React Native menggunakan `react-test-renderer`. Tidak menguji rendering native views (seperti `UIView` di iOS atau `android.view.View` di Android), melainkan menguji perubahan pohon JSON internal, trigger native synthetic events, dan efek samping pada status state store.
3.  **Blackbox End-to-End Tests (Maestro)**: Mengompilasi aplikasi utuh, menginstalnya ke simulator iOS atau emulator Android di lingkungan CI, dan mengeksekusi aksi berbasis Accessibility API OS. Maestro mengevaluasi pohon elemen native sesungguhnya, mengabaikan apakah aplikasi dibuat dengan React Native, Flutter, atau Native murni.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah konfigurasi CI terintegrasi penuh untuk pengujian unit dan komponen menggunakan GitHub Actions, Jest, dan RNTL.

### 1. `jest.config.js`
Menangani pemetaan modul, transformasi TypeScript, dan pembersihan mock native.

```javascript
/** @type {import('jest').Config} */
module.exports = {
  preset: 'react-native',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.ts'],
  transformIgnorePatterns: [
    'node_modules/(?!(jest-)?react-native|@react-native|@react-navigation|@react-native-community)',
  ],
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json', 'node'],
  collectCoverageFrom: [
    'src/**/*.{ts,tsx}',
    '!src/**/*.d.ts',
    '!src/**/*.stories.{ts,tsx}',
    '!src/types/**',
  ],
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 85,
      lines: 85,
      statements: 85,
    },
  },
};
```

### 2. `jest.setup.ts`
Mocking native layer kritis agar ekosistem Jest tidak mengalami memory-fault atau unhandled rejection.

```typescript
import '@testing-library/react-native/extend-expect';

// Mocking Native Animated Driver untuk mencegah error async loop
jest.mock('react-native/Libraries/Animated/NativeAnimatedHelper');

// Mocking TurboModule / NativeModule dasar (PlatformConstants)
jest.mock('react-native/Libraries/Utilities/Platform', () => {
  const Platform = jest.requireActual('react-native/Libraries/Utilities/Platform');
  Platform.constants = {
    ...Platform.constants,
    reactNativeVersion: { major: 0, minor: 76, patch: 0 },
  };
  return Platform;
});

// Setup mock global fetch jika digunakan di unit tests
global.fetch = jest.fn(() =>
  Promise.resolve({
    json: () => Promise.resolve({ success: true }),
    ok: true,
    status: 200,
  })
) as jest.Mock;
```

### 3. `src/components/PaymentTransfer.test.tsx`
Contoh pengujian komponen integrasi fungsional menggunakan RNTL.

```typescript
import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react-native';
import { PaymentTransfer } from './PaymentTransfer';

describe('PaymentTransfer Component Integration Test', () => {
  const mockOnSubmit = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders input elements and handles submit with valid amount', async () => {
    const { getByTestId, getByText } = render(
      <PaymentTransfer maxLimit={5000000} onExecuteTransfer={mockOnSubmit} />
    );

    const amountInput = getByTestId('input-transfer-amount');
    const submitButton = getByTestId('button-transfer-submit');

    // Coba input melebihi limit
    fireEvent.changeText(amountInput, '6000000');
    fireEvent.press(submitButton);

    await waitFor(() => {
      expect(getByText('Jumlah transfer melebihi batas limit transaksi.')).toBeTruthy();
      expect(mockOnSubmit).not.toHaveBeenCalled();
    });

    // Input valid
    fireEvent.changeText(amountInput, '2500000');
    fireEvent.press(submitButton);

    await waitFor(() => {
      expect(mockOnSubmit).toHaveBeenCalledTimes(1);
      expect(mockOnSubmit).toHaveBeenCalledWith(2500000);
    });
  });
});
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Bedah File: `jest.config.js`
*   **Baris 4 (`preset: 'react-native'`):** Mengaktifkan preset bawaan React Native yang menyuntikkan transformer Babel spesifik untuk kode JSX dan arsitektur Hermes.
*   **Baris 5 (`setupFilesAfterEnv: ['<rootDir>/jest.setup.ts']`):** Menjalankan file registrasi ekstensi matcher (seperti matcher kustom `@testing-library/jest-native`) setelah lingkungan runtime Jest diinisialisasi sepenuhnya.
*   **Baris 6-8 (`transformIgnorePatterns`):** Secara default, Jest mengabaikan transformasi semua file di dalam `node_modules`. Regex negatif `(?!(...))` menginstruksikan Jest untuk *tetap mentranspilasi* package-package spesifik seperti React Native dan sub-ekosistemnya yang didistribusikan dalam format source ES Module modern tanpa kompilasi internal.
*   **Baris 16-23 (`coverageThreshold`):** Mencegah degradasi kualitas sistem. Jika metrik *code coverage* turun di bawah 80% pada branch CI, proses pipeline otomatis memicu *exit code 1* dan menggagalkan merge pull request.

### Bedah File: `PaymentTransfer.test.tsx`
*   **Baris 13-15 (`render(...)`):** Merender instance virtual tree dari komponen. Operasi ini tidak memerlukan emulator native, mengonversi struktur React Native element menjadi JavaScript Object tree.
*   **Baris 17-18 (`getByTestId(...)`):** Mengambil referensi elemen native menggunakan atribut `testID`. Praktik ini tahan terhadap refaktorisasi styling atau lokalisasi bahasa, tidak seperti pencarian berbasis teks statis.
*   **Baris 21 (`fireEvent.changeText(...)`):** Memicu pemanggilan event handler `onChangeText` secara sinkron pada elemen input, mensimulasikan pengetikan pengguna pada keypad native.
*   **Baris 24-27 (`await waitFor(...)`):** Menghindari kondisi *race condition* pada pembaruan state asinkron. Runner akan melakukan polling fungsi assertions hingga kondisi terpenuhi atau batas timeout tercapai.

---

## SEKSI 09 — STUDI KASUS NYATA

### Konteks: Aplikasi Pembayaran Skala Enterprise "PayNusantara"
Aplikasi enterprise React Native "PayNusantara" melayani 12 juta transaksi per bulan. Sebelumnya, tim mobile merilis aplikasi secara manual dari laptop engineer. Hal ini menimbulkan insiden produksi kritis:
1.  **Artifact Desynchronization**: Tim merilis versi iOS dengan skema API v2, tetapi biner Android tertinggal dan masih menembak API v1 yang sudah didepresiasi.
2.  **Keystore Poisoning & Loss**: Keystore produksi lokal tersimpan di harddisk workstation developer utama. Saat workstation mengalami kerusakan perangkat keras, rilis Android tertunda 3 minggu hingga proses pemulihan kunci di Google Play Support selesai.
3.  **Human Error Sign-off**: Engineer lupa memperbarui `CFBundleVersion` di Info.plist iOS, menyebabkan Apple Transporter menolak biner saat build malam hari, menunda jadwal peluncuran fitur compliance Bank Indonesia.

### Solusi Rekayasa
Membangun arsitektur CI/CD terpusat menggunakan **GitHub Actions Enterprise Self-Hosted Runner Infrastructure** yang dikombinasikan dengan **Fastlane Pipelines**:
*   *Trunk-Based Release Flow*: Branch `main` mencerminkan versi produksi. Pembuatan tag semantic (`vX.Y.Z`) memicu orkestrasi build native paralel secara otomatis.
*   *Headless End-to-End Testing*: Mengintegrasikan Maestro CLI pada simulator CI untuk menjalankan 40 skenario pengujian transaksi sebelum rilis binary disetujui.
*   *Zero-Key On-Premises*: Kunci enkripsi dan sertifikat penandatanganan dikelola sepenuhnya di HashiCorp Vault dan disuntikkan ke runner via runtime environment variables tanpa tersimpan di storage disk runner.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi menyeluruh sistem build dan rilis kelas industri:

### 1. `fastlane/Fastfile`
Konfigurasi terpadu untuk iOS dan Android.

```ruby
default_platform(:android)

platform :android do
  desc "Kompilasi dan Distribusi Android App Bundle ke Google Play Store (Internal Track)"
  lane :build_and_deploy_internal do |options|
    version_code = options[:version_code] || prompt(text: "Masukkan Version Code: ")
    version_name = options[:version_name] || prompt(text: "Masukkan Version Name: ")

    # Persiapkan Gradle Properties untuk signing
    gradle(
      task: "bundle",
      build_type: "Release",
      project_dir: "./android",
      properties: {
        "android.injected.version.code" => version_code,
        "android.injected.version.name" => version_name,
        "MYAPP_UPLOAD_STORE_FILE" => ENV["ANDROID_KEYSTORE_PATH"],
        "MYAPP_UPLOAD_KEY_ALIAS" => ENV["ANDROID_KEY_ALIAS"],
        "MYAPP_UPLOAD_STORE_PASSWORD" => ENV["ANDROID_KEYSTORE_PASSWORD"],
        "MYAPP_UPLOAD_KEY_PASSWORD" => ENV["ANDROID_KEY_PASSWORD"],
      }
    )

    # Distribusi otomatis ke Play Console API
    upload_to_play_store(
      track: "internal",
      package_name: "com.paynusantara.app",
      aab: "./android/app/build/outputs/bundle/release/app-release.aab",
      json_key_data: ENV["PLAY_STORE_JSON_KEY"],
      skip_waiting_for_build_processing: true
    )
  end
end

platform :ios do
  desc "Kompilasi dan Distribusi IPA ke TestFlight"
  lane :build_and_deploy_testflight do |options|
    app_store_connect_api_key(
      key_id: ENV["APP_STORE_CONNECT_KEY_ID"],
      issuer_id: ENV["APP_STORE_CONNECT_ISSUER_ID"],
      key_content: ENV["APP_STORE_CONNECT_API_KEY_CONTENT"],
      duration: 1200,
      in_house: false
    )

    # Sinkronisasi Sertifikat via Match (Read-Only Mode di CI)
    match(
      type: "appstore",
      storage_mode: "git",
      git_url: ENV["MATCH_GIT_URL"],
      readonly: true,
      shallow_clone: true
    )

    # Increment nomor build otomatis
    increment_build_number(
      build_number: options[:build_number] || ENV["GITHUB_RUN_NUMBER"],
      xcodeproj: "./ios/PayNusantara.xcodeproj"
    )

    # Kompilasi & Penandatanganan Arsip Xcode
    gym(
      scheme: "PayNusantara",
      workspace: "./ios/PayNusantara.xcworkspace",
      clean: true,
      output_directory: "./ios/build",
      output_name: "PayNusantara.ipa",
      export_method: "app-store",
      export_options: {
        provisioningProfiles: {
          "com.paynusantara.app" => "match AppStore com.paynusantara.app"
        }
      }
    )

    # Upload ke Apple TestFlight
    upload_to_testflight(
      skip_waiting_for_build_processing: false,
      apple_id: ENV["APPLE_APP_ID"],
      ipa: "./ios/build/PayNusantara.ipa"
    )
  end
end
```

### 2. `.maestro/flows/payment_flow.yaml`
Skrip automasi End-to-End Test Maestro UI tanpa flake.

```yaml
appId: com.paynusantara.app
---
- launchApp:
    clearState: true
- assertVisible: "Selamat Datang di PayNusantara"

# Navigasi ke Layar Transfer
- tapOn:
    id: "nav-button-transfer"
- assertVisible: "Kirim Dana Cepat"

# Input Nominal
- tapOn:
    id: "input-transfer-amount"
- inputText: "750000"
- hideKeyboard

# Submit Transaksi
- tapOn:
    id: "button-transfer-submit"

# Validasi Modal Konfirmasi Native
- assertVisible: "Konfirmasi Pemindahan Saldo"
- tapOn: "LANJUTKAN OTORISASI"

# Verifikasi Layar Berhasil
- extendedWaitUntil:
    visible:
      id: "state-transaction-success"
    timeout: 10000
- assertVisible: "Transaksi Anda Berhasil Diterbitkan"
```

### 3. `.github/workflows/deploy.yml`
Pipeline orkestrasi rilis lengkap lintas platform.

```yaml
name: Mobile Release Engineering Pipeline

on:
  push:
    tags:
      - 'v*.*.*'

concurrency:
  group: release-${{ github.ref }}
  cancel-in-progress: true

jobs:
  quality-gate:
    name: Code Quality & Automated Tests
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Setup Node.js Environment
        uses: actions/setup-node@v4
        with:
          node-version-file: '.node-version'
          cache: 'yarn'

      - name: Install Dependencies
        run: yarn install --immutable

      - name: Static Analysis (Lint & Types)
        run: |
          yarn eslint src/ --max-warnings 0
          yarn tsc --noEmit

      - name: Run Unit & Integration Tests
        run: yarn test --coverage --ci --maxWorkers=4

  android-release:
    name: Build & Distribute Android (AAB)
    needs: quality-gate
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Setup Java Development Kit (Temurin 17)
        uses: actions/setup-java@v4
        with:
          distribution: 'temurin'
          java-version: '17'

      - name: Setup Android SDK
        uses: android-actions/setup-android@v3

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version-file: '.node-version'
          cache: 'yarn'

      - name: Install Dependencies
        run: yarn install --immutable

      - name: Setup Ruby for Fastlane
        uses: ruby/setup-ruby@v1
        with:
          ruby-version: '3.2'
          bundler-cache: true

      - name: Decode Android Keystore
        run: |
          echo "${{ secrets.ANDROID_KEYSTORE_BASE64 }}" | base64 --decode > android/app/release.keystore
        env:
          ANDROID_KEYSTORE_BASE64: ${{ secrets.ANDROID_KEYSTORE_BASE64 }}

      - name: Run Fastlane Deployment
        env:
          ANDROID_KEYSTORE_PATH: "release.keystore"
          ANDROID_KEY_ALIAS: ${{ secrets.ANDROID_KEY_ALIAS }}
          ANDROID_KEYSTORE_PASSWORD: ${{ secrets.ANDROID_KEYSTORE_PASSWORD }}
          ANDROID_KEY_PASSWORD: ${{ secrets.ANDROID_KEY_PASSWORD }}
          PLAY_STORE_JSON_KEY: ${{ secrets.PLAY_STORE_JSON_KEY }}
        run: |
          bundle exec fastlane android build_and_deploy_internal \
            version_code:${{ github.run_number }} \
            version_name:${{ github.ref_name }}

  ios-release:
    name: Build & Distribute iOS (IPA)
    needs: quality-gate
    runs-on: macos-14
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version-file: '.node-version'
          cache: 'yarn'

      - name: Install Node Dependencies
        run: yarn install --immutable

      - name: Setup Ruby & Bundler
        uses: ruby/setup-ruby@v1
        with:
          ruby-version: '3.2'
          bundler-cache: true

      - name: Select Xcode 15.4
        run: sudo xcode-select -s /Applications/Xcode_15.4.app

      - name: Cache CocoaPods Pods
        uses: actions/cache@v4
        with:
          path: ios/Pods
          key: ${{ runner.os }}-pods-${{ hashFiles('ios/Podfile.lock') }}
          restore-keys: |
            ${{ runner.os }}-pods-

      - name: Install CocoaPods
        run: |
          cd ios
          pod install --repo-update

      - name: Run Fastlane Deployment
        env:
          APP_STORE_CONNECT_KEY_ID: ${{ secrets.APP_STORE_CONNECT_KEY_ID }}
          APP_STORE_CONNECT_ISSUER_ID: ${{ secrets.APP_STORE_CONNECT_ISSUER_ID }}
          APP_STORE_CONNECT_API_KEY_CONTENT: ${{ secrets.APP_STORE_CONNECT_API_KEY_CONTENT }}
          MATCH_GIT_URL: ${{ secrets.MATCH_GIT_URL }}
          MATCH_PASSWORD: ${{ secrets.MATCH_PASSWORD }}
          MATCH_GIT_BASIC_AUTHORIZATION: ${{ secrets.MATCH_GIT_TOKEN_BASE64 }}
          APPLE_APP_ID: ${{ secrets.APPLE_APP_ID }}
        run: |
          bundle exec fastlane ios build_and_deploy_testflight \
            build_number:${{ github.run_number }}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

### 1. Framework Pengujian End-to-End: Detox vs. Maestro vs. Appium

| Dimensi Arsitektur | Appium | Detox | Maestro |
| :--- | :--- | :--- | :--- |
| **Model Eksekusi** | Eksternal (WebDriver HTTP Wire) | Gray-Box (In-Process Native Synchronization) | Black-Box Native Accessibility Engine |
| **Flakiness (Ketidakstabilan)** | Tinggi (Sering timeout jika animasi lambat) | Sangat Rendah (Menunggu idle thread UI & JS otomatis) | Rendah (Pencarian elemen deterministik dan retry native) |
| **Dukungan React Native Baru** | Agnostik | Rentan pecah saat migrasi New Architecture (TurboModules) | Stabil, independen terhadap engine JS internal |
| **Kecepatan Setup CI** | Kompleks (Perlu Appium Server + WebDrivers) | Rumit (Perlu rebuild wrapper binary native via Detox CLI) | Sangat Cepat (Satu binary CLI tunggal tanpa konfigurasi SDK rumit) |
| **Bahasa Penulisan Skenario** | JS, Python, Java | JavaScript / TypeScript | Deklaratif YAML |

### 2. Strategi Code Signing iOS: Manual vs. Apple Managed vs. Fastlane Match

| Parameter | Manual Signing | Xcode Automatic (Cloud Managed) | Fastlane Match (Git Vault) |
| :--- | :--- | :--- | :--- |
| **Keandalan CI/CD** | Sangat Rendah (Sertifikat manual kadaluarsa di CI) | Menengah (Gagal jika akun butuh autentikasi 2FA berkala) | Deterministik & Industri Standar |
| **Audit Jejak Keamanan** | Sulit diaudit (File `.p12` berpindah-pindah manual) | Tertutup dalam sistem Apple Developer Portal | Sangat Tinggi (Git commit log terenkripsi OpenSSL) |
| **Onboarding Tim Baru** | 1-2 hari (Eksport/Import private key manual) | Cepat (Namun sering terjadi duplikasi sertifikat di portal) | 1 Perintah CLI (`fastlane match development --readonly`) |
| **Dampak Sertifikat Kadaluarsa** | Biner produksi ditolak mendadak | Terisolasi | Cukup 1 anggota tim merotasi kunci, seluruh CI otomatis terupdate |

---

## SEKSI 12 — EDGE CASES & PITFALLS

### 1. "Missing or Invalid Signature" pada CocoaPods Dynamic Frameworks
*   **Gejala**: Apple mentransmisikan email penolakan setelah build terunggah: *"Invalid Code Signing Entitlements / Framework Binary Not Signed"*.
*   **Akar Masalah**: Library native modular yang diinstal via CocoaPods memiliki konfigurasi `CODE_SIGNING_ALLOWED = YES` saat diarsip di mesin runner, bertabrakan dengan penandatanganan level root target gym.
*   **Mitigasi**: Tambahkan post-install hook deterministik pada file `ios/Podfile`:

```ruby
post_install do |installer|
  installer.pods_project.targets.each do |target|
    target.build_configurations.each do |config|
      config.build_settings['CODE_SIGNING_ALLOWED'] = 'NO'
      config.build_settings['CODE_SIGNING_REQUIRED'] = 'NO'
    end
  end
