# SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 03-Frontend-and-Mobile
*   **Topik:** Flutter Enterprise Engineering
*   **Bab:** 10 — Release Engineering, Operational Excellence, & Enterprise Scale
*   **Modul:** 01
*   **Judul:** DevSecOps, Continuous Delivery, & Observability
*   **Tingkat Kesulitan:** Advanced / Staff Engineer Level
*   **Prasyarat:** Pemahaman mendalam tentang arsitektur Flutter Engine/Framework, State Management, Platform Channels (Android NDK/JVM, iOS Mach-O/Swift), REST/gRPC Network Layers, serta penguasaan dasar CI/CD runner environments (Linux/macOS).

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta ajar diharapkan mampu:

1.  **Membangun Pipeline DevSecOps Otomatis:** Mengintegrasikan SAST (Static Application Security Testing), Secret Scanning, Dependency Vulnerability Scanning, DAST baseline, dan Binary Hardening secara headless pada pipeline CI/CD (GitHub Actions / GitLab CI).
2.  **Mengarsitekturi Continuous Delivery Lintas Platform:** Mengonfigurasi Fastlane, Match (Code Signing iOS via Git Storage terenkripsi), Android Keystore injection terisolasi, serta orkestrasi distribusi otomatis ke Google Play Internal App Sharing dan Apple TestFlight.
3.  **Mengimplementasikan Tracing & Error Telemetry Lintas Batas (Cross-Boundary):** Menghubungkan pelaporan crash dari Dart Runtime layer ke Native Layer (C/C++, JVM, Objective-C/Swift) hingga APM (Sentry/OpenTelemetry) dengan penanganan Zone mismatch dan unhandled asynchronous exceptions.
4.  **Menegakkan Kebijakan Reproducible Builds & Supply Chain Security:** Menerapkan Software Bill of Materials (SBOM) generation (CycloneDX/SPDX), penguncian hash artifact, serta pemisahan kredensial menggunakan prinsip *Zero-Trust build runners*.

---

# SEKSI 03 — MINDSET & MENTAL MODEL

### Shift-Left Engineering dalam Ekosistem Client-Side
Dalam arsitektur backend, patch kerentanan dapat diterapkan secara instan ke armada server via rolling deployment. Pada ekosistem Flutter (Mobile), aplikasi adalah **untrusted client** yang didistribusikan ke perangkat pihak ketiga di luar kendali infrastruktur internal:
*   *Binary final terekspos langsung* terhadap dekompilasi, reverse engineering, dan manipulasi memori runtime.
*   *Time-to-Remediate (MTTR) berhari-hari*, dibatasi oleh siklus tinjauan toko aplikasi (App Store Review & Google Play Policy Enforcement) serta kecepatan adopsi update oleh pengguna akhir.

Oleh karena itu, pola pikir engineering bergeser: **Keamanan dan Verifikasi Kualitas dipindahkan sepenuhnya ke fase kompilasi dan CI (Shift-Left)**. Setiap commit diperlakukan sebagai kandidat rilis yang berpotensi memiliki celah zero-day dan regresi performa fatal.

### Triad Observabilitas Aplikasi Mobile
Observabilitas mobile bukan sekadar mencatat log via `debugPrint()`:
1.  **Metrics:** Alokasi frame rendering (jank 16ms/60fps vs 8.3ms/120fps), memory footprint (RSS/Dart Heap size), CPU usage, dan network bandwidth metrics.
2.  **Logs:** Structured contextual logging yang secara otomatis menghapus PII (Personally Identifiable Information) sebelum persistensi lokal atau transmisi over-the-wire.
3.  **Traces:** Distributed Context Tracing (W3C TraceContext standards) yang menghubungkan trace ID dari interaksi UI di Flutter, menembus platform channel, memicu request jaringan, hingga trace backend microservices.

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

```
                                      PIPELINE DEVSECOPS & CONTINUOUS DELIVERY
                                      
  [Developer Machine]
          │
          ├─► git push origin feature/fintech-core
          ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│ GITHUB ACTIONS / CI RUNNER (ISOLATED EPHEMERAL CONTAINER)                                     │
│                                                                                                │
│  PHASE 1: SECURE LINT & STATIC ANALYSIS (PARALLEL EXECUTION)                                   │
│  ┌────────────────────────┐  ┌────────────────────────┐  ┌──────────────────────────────────┐  │
│  │ Gitleaks / TruffleHog  │  │ Flutter Analyze        │  │ OSV-Scanner / Nancy              │  │
│  │ (Zero-Trust Scan Token)│  │ (Custom Strict Rules)  │  │ (pubspec.lock CVE Audit)         │  │
│  └───────────┬────────────┘  └───────────┬────────────┘  └────────────────┬─────────────────┘  │
│              └───────────────────────────┼────────────────────────────────┘                    │
│                                          ▼                                                     │
│  PHASE 2: DETERMINISTIC TESTING & INTEGRATION COVERAGE                                         │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ - Unit, Widget & Golden Contract Tests (flutter test --coverage)                         │  │
│  │ - Enforcement: Minimum Line Coverage >= 85%, Zero Floating-point Golden Pixel Diff      │  │
│  └───────────────────────────────────────┬──────────────────────────────────────────────────┘  │
│                                          ▼                                                     │
│  PHASE 3: SECURE BUILD, HARDENING, & SBOM GENERATION                                           │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ - Inject Keystore / Apple App Store Provisioning via Vault / Match                       │  │
│  │ - ProGuard / R8 Rule Optimization + NDK Strip Symbols                                    │  │
│  │ - Obfuscation Flag: --obfuscate --split-debug-info=./v1.0.0-symbols                      │  │
│  │ - CycloneDX: Generasi SBOM (Software Bill of Materials)                                  │  │
│  └───────────────────────────────────────┬──────────────────────────────────────────────────┘  │
│                                          │                                                     │
│                  ┌───────────────────────┴───────────────────────┐                             │
│                  ▼                                               ▼                             │
│  [Android Target: AAB]                           [iOS Target: IPA]                             │
│  - Keystore Signer (v2/v3 scheme)                - Fastlane Match (Enterprise Keychain)       │
│  - Upload Mapping File ke Sentry                 - Upload dSYM Symbols ke Sentry               │
└──────────────────┬───────────────────────────────────────────────┬─────────────────────────────┘
                   │                                               │
                   ▼                                               ▼
┌──────────────────────────────────────┐       ┌─────────────────────────────────────────────────┐
│ Google Play Console                  │       │ Apple App Store Connect                         │
│ (Internal Testing Track)             │       │ (TestFlight Distribution Track)                 │
└──────────────────┬───────────────────┘       └───────────────────┬─────────────────────────────┘
                   │                                               │
                   └───────────────────────┬───────────────────────┘
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│ RUNTIME OBSERVABILITY & TELEMETRY MESH (END-USER RUNTIME)                                      │
│                                                                                                │
│   Flutter App (Dart Engine) ───[Zone / Platform Channel]───► Native Layer (C++ / ObjC / Kotlin)│
│              │                                                                │                │
│              ├─► Structured Logger (PII Masking Filter Engine)               │                │
│              ├─► OpenTelemetry Trace Exporter (W3C Header Traceparent)        │                │
│              └─► Sentry SDK Hub ──(Crash, ANR, Native Signal, Memory Dump)────┘                │
│                         │                                                                      │
│                         ▼ (Encrypted HTTPS Pipeline)                                           │
│          ┌─────────────────────────────┐                                                       │
│          │ Sentry / Datadog / OTel APM │                                                       │
│          └─────────────────────────────┘                                                       │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### 1. Flutter Error Handling Mechanics (Zone, PlatformDispatcher, FlutterError)
Terdapat tiga layer isolasi penanganan eror runtime di Flutter:
*   **`FlutterError.onError`**: Menangkap uncaught exceptions yang berasal dari siklus hidup *Flutter Framework* (contoh: crash pada method `build()`, layout failure, parsing widget tree). Ini default-nya mencetak ke console melalui `FlutterError.dumpErrorToConsole`.
*   **`PlatformDispatcher.instance.onError`**: Diperkenalkan untuk menggantikan penanganan raw zone error. Callback ini menangkap *asynchronous unhandled exceptions* yang lolos dari framework langsung pada Dart root isolate level (contoh: `Future.error` yang tidak ditangani try-catch). Jika mengembalikan `true`, eror dianggap ditangani dan proses dicegah dari crash fatal.
*   **`runZonedGuarded`**: Mekanisme eksekusi berbasis *Zone context*. Membawa state terisolasi (Zone-local values) dan mendefinisikan boundary asynchronous error handler. Penting untuk memetakan context request ID dan mengisolasi unhandled futures di micro-task queue.

### 2. Fastlane Match & Keystore Signing Decoupling
*   **iOS (Fastlane Match):** Memecahkan paradigma manual provisioning profile yang rapuh. Match mengimplementasikan filosofi *Git-as-single-source-of-truth*. Satu repository Git privat terpisah menyimpan sertifikat distribusi dan provisioning profiles yang dienkripsi menggunakan OpenSSL (AES-256-CBC). Mesin CI melakukan kloning repositori, mendekripsi certificate menggunakan passphrase yang disimpan dalam CI Secret, membuat keychain sementara (ephemeral keychain), mengimpor sertifikat, dan menghapus keychain segera setelah proses packaging IPA selesai.
*   **Android Code Signing:** Kunci rilis (.keystore / .jks) **tidak boleh** dikomit ke Git. File fisik di-encode ke format Base64 dan disimpan di Secrets Manager. Pada fase CI, script mendekode string Base64 kembali menjadi file biner di direktori terisolasi runner (`/tmp/keystore.jks`), lalu variabel `KEYSTORE_PASSWORD`, `KEY_ALIAS`, dan `KEY_PASSWORD` diinjeksikan secara real-time melalui *Gradle Project Properties* atau environment variables, mencegah footprint file permanen.

### 3. Binary Obfuscation & Native Debug Symbols Mechanics
Ketika flag `--obfuscate --split-debug-info=./symbols` dipanggil:
*   Dart AOT compiler (pada fase kompilasi arsitektur ARM64) menghapus seluruh nama fungsi, method, class, dan identifier, menggantikannya dengan token yang tidak bermakna (`x0`, `a`, `b`).
*   Mapping dari token-token acak ini ke baris kode aktual disimpan ke dalam berkas metadata symbol (*symbol table mapping*).
*   Jika aplikasi crash pada perangkat produksi, stack trace hanya akan menampilkan angka memori acak atau token yang telah terobfuscasi (contoh: `app.so!x0192a8`).
*   Pipeline CI wajib mengekstrak berkas `.symbols` (untuk Android dan Linux) serta `.dSYM` (untuk iOS macOS Mach-O binary) dan mengunggahnya secara headless ke Sentry/Crashlytics API. Tanpa file ini, stack trace produksi tidak dapat dide-simbolisasi (symbolicated).

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Software Supply Chain Security (SLSA Framework & SBOM)
Aplikasi Flutter modern mengonsumsi puluhan hingga ratusan pustaka pihak ketiga dari `pub.dev`. Sebuah vulnerabilitas atau *malicious takeover* pada package transitif dapat mengompromikan keamanan aplikasi secara keseluruhan.
*   **CycloneDX SBOM:** Software Bill of Materials (SBOM) adalah inventaris lengkap seluruh komponen kode, dependensi open-source, versi dependensi, dan lisensi yang digunakan dalam aplikasi.
*   Alat audit statis (`osv-scanner`) mengekstrak snapshot dependensi dari `pubspec.lock` dan mencocokkannya ke database Google Open Source Vulnerabilities (OSV) secara real-time pada tahap linting CI runner. Jika dependensi memiliki CVE kritis tanpa patch, pipeline otomatis *hard-fail*.

### Obfuscation & R8/ProGuard Shrunken Architecture
Pipeline kompilasi produksi Flutter melibatkan dua layer compiler:
1.  **Dart AOT Compiler:** Mengompilasi Dart source code menjadi native assembly (`libapp.so` untuk Android, `App.framework` Mach-O binary untuk iOS).
2.  **Native Platform Compiler (R8 / ProGuard / LLVM Clang):** Pada Android, file bytecode JVM (`classes.dex`) dan resource XML diminifikasi dan dioptimasi oleh R8 engine. R8 menganalisis dependensi kelas native Flutter (`io.flutter.app.*`) dan menghapus kode yang tidak terpakai (tree shaking).
*Risiko Arsitektural:* Jika rule R8 terlalu agresif, platform interface class yang dipanggil via reflection oleh method channel akan terhapus, menyebabkan runtime crash `NoSuchMethodError` saat rilis. Pipeline CI wajib menguji *Release build mode* secara berkala, bukan sekadar *Debug build*.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah konfigurasi CI/CD Declarative menggunakan **GitHub Actions** untuk orkestrasi build multi-platform, verifikasi audit keamanan, pengujian deterministik, pembuatan SBOM, dan kompilasi obfuscated binary.

### `.github/workflows/production_pipeline.yml`

```yaml
name: Production DevSecOps & Deployment Pipeline

on:
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  security-audit-and-lint:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Java Environment (JDK 17)
        uses: actions/setup-java@v4
        with:
          distribution: 'temurin'
          java-version: '17'

      - name: Setup Flutter Engine Environment
        uses: subosito/flutter-action@v2
        with:
          flutter-version: '3.19.6'
          channel: 'stable'
          cache: true

      - name: Run Secret Scanning (Gitleaks)
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Pubspec Dependency Validation & Vulnerability Audit
        run: |
          flutter pub get
          curl -sSfL https://github.com/google/osv-scanner/releases/download/v1.7.0/osv-scanner_linux_amd64 -o osv-scanner
          chmod +x osv-scanner
          ./osv-scanner --lockfile=pubspec.lock

      - name: Static Analysis Enforcement
        run: flutter analyze --fatal-infos --fatal-warnings

      - name: Deterministic Unit & Widget Testing
        run: flutter test --coverage --coverage-path=./coverage/lcov.info

      - name: Validate Coverage Threshold (Min 85%)
        run: |
          sudo apt-get update && sudo apt-get install -y lcov
          lcov --summary ./coverage/lcov.info | grep "lines......" | awk '{print $2}' | sed 's/%//' | awk '{if ($1 < 85.0) exit 1}'

  build-and-sign-android:
    needs: security-audit-and-lint
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-java@v4
        with:
          distribution: 'temurin'
          java-version: '17'

      - uses: subosito/flutter-action@v2
        with:
          flutter-version: '3.19.6'
          channel: 'stable'
          cache: true

      - name: Decode Android Keystore
        env:
          KEYSTORE_BASE64: ${{ secrets.ANDROID_KEYSTORE_BASE64 }}
        run: |
          echo "$KEYSTORE_BASE64" | base64 --decode > android/app/keystore.jks

      - name: Build Android App Bundle (AAB) with Obfuscation
        env:
          KEYSTORE_PASSWORD: ${{ secrets.ANDROID_KEYSTORE_PASSWORD }}
          KEY_ALIAS: ${{ secrets.ANDROID_KEY_ALIAS }}
          KEY_PASSWORD: ${{ secrets.ANDROID_KEY_PASSWORD }}
        run: |
          flutter build appbundle --release \
            --obfuscate \
            --split-debug-info=./android-symbols \
            --extra-gen-snapshot-options=--save-obfuscation-map=./android-symbols/app.map

      - name: Upload Symbols Artifact
        uses: actions/upload-artifact@v4
        with:
          name: android-debug-symbols
          path: ./android-symbols/

      - name: Clean Keystore Footprint
        if: always()
        run: rm -f android/app/keystore.jks
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

### Analisis `.github/workflows/production_pipeline.yml`

*   `concurrency: group: ${{ ... }}, cancel-in-progress: true`: Mencegah pemborosan resource runner. Jika commit baru dipush pada branch yang sama saat pipeline sedang berjalan, commit lama langsung dibatalkan.
*   `fetch-depth: 0`: Menginstruksikan Git untuk menarik seluruh riwayat commit, bukan shallow copy. Ini krusial bagi engine secret-scanning (Gitleaks) untuk memindai riwayat commit historis terhadap kebocoran secret masa lalu.
*   `osv-scanner --lockfile=pubspec.lock`: Memeriksa file dependensi terkunci (`pubspec.lock`) terhadap database CVE terbuka secara deterministik tanpa mengeksekusi script pihak ketiga yang tidak tepercaya.
*   `flutter analyze --fatal-infos --fatal-warnings`: Menaikkan severity level analisis Dart. Bahkan peringatan minor (infos) langsung menggagalkan pipeline, memaksakan standar kebersihan kode mutlak.
*   `lcov --summary ... | awk '{if ($1 < 85.0) exit 1}'`: Gate penegakan metrik. Jika test coverage baris turun di bawah 85%, pipeline langsung terhenti (exit code 1), memblokir artifact promosi ke stage rilis.
*   `echo "$KEYSTORE_BASE64" | base64 --decode > android/app/keystore.jks`: Mengonversi credential Android dari environment variable aman runner ke bentuk biner sementara di path yang diisolasi.
*   `flutter build appbundle --release --obfuscate --split-debug-info=./android-symbols`:
    *   `--release`: Mengaktifkan optimalisasi compiler AOT penuh (AOT Snapshot generation).
    *   `--obfuscate`: Mengaktifkan penggantian nama identifier menjadi stripped hashes.
    *   `--split-debug-info`: Memisahkan tabel simbol keluar dari binary binary AAB, menyusutkan ukuran aplikasi serta mencegah ekstraksi simbol di runtime perangkat target.
*   `if: always() -> rm -f android/app/keystore.jks`: Langkah post-build wajib. Menghapus keystore biner terdekripsi terlepas dari apakah proses build berhasil, gagal, atau dibatalkan, mematuhi prinsip hygiene sistem berkas.

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario: Arsitektur Pipeline Continuous Deployment SuperApp FinTech
**Perusahaan:** PT FinTech Nusantara (Skala: 12 Juta MAU).  
**Kondisi Awal:**
*   Rilis manual via laptop developer; sertifikat disimpan lokal di mesin lead engineer.
*   Crash reporting native (Kotlin/Swift) dan Dart terpisah pada dua dashboard berbeda tanpa korelasi.
*   Kebocoran runtime credential terjadi ketika token internal API terdorong ke production via Dart constant flags.
*   Review Google Play menolak update karena ditemukannya transitive vulnerability CVE lama pada package file picker.

**Solusi Arsitektur:**
1.  **Pemisahan Zero-Trust Environment:** Kunci rilis dipindahkan ke HashiCorp Vault. Mesin CI (macOS dan Linux bare-metal runners) mengambil ephemeral credentials via OpenID Connect (OIDC).
2.  **Sentry Telemetry Mesh Integration:** Membangun *Crash & Performance Tracking Layer* terpadu. Error Dart Isolate, error asynchronous unhandled, dan signal panic C++ NDK di-wrap dalam trace context terdistribusi seragam yang memetakan user session tanpa menyimpan PII.
3.  **Fastlane Match Automation:** Orkestrasi rilis TestFlight iOS headless memanfaatkan containerized fastlane runner dengan dynamic profile provisioning.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi komprehensif implementasi telemetri enterprise, structured logging dengan perlindungan data pribadi (PII), Fastlane orchestration, dan global error boundaries pada Dart.

### 1. `lib/core/observability/pii_masker.dart` (Sanitisasi Data)

```dart
/// Utility engine untuk mendeteksi dan melakukan masking data sensitif (PII)
/// sebelum dikirimkan ke observability dashboard atau file log lokal.
final class PiiMasker {
  PiiMasker._();

  static final RegExp _emailRegex = RegExp(
    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    caseSensitive: false,
  );

  static final RegExp _creditCardRegex = RegExp(
    r'\b(?:\d[ -]*?){13,16}\b',
  );

  static final RegExp _bearerTokenRegex = RegExp(
    r'Bearer\s+[A-Za-z0-9\-._~+/]+=*',
    caseSensitive: false,
  );

  /// Memfilter payload string dan mengganti nilai sensitif dengan hashing/token statis
  static String mask(String payload) {
    if (payload.isEmpty) return payload;

    var sanitized = payload.replaceAllMapped(_emailRegex, (match) {
      final email = match.group(0)!;
      final parts = email.split('@');
      final name = parts[0];
      final domain = parts[1];
      final maskedName = name.length > 2
          ? '${name.substring(0, 2)}***'
          : '***';
      return '$maskedName@$domain';
    });

    sanitized = sanitized.replaceAllMapped(_creditCardRegex, (match) {
      final rawCard = match.group(0)!.replaceAll(RegExp(r'[\s-]'), '');
      if (rawCard.length < 12) return match.group(0)!;
      final lastFour = rawCard.substring(rawCard.length - 4);
      return '****-****-****-$lastFour';
    });

    sanitized = sanitized.replaceAllMapped(_bearerTokenRegex, (_) {
      return 'Bearer [REDACTED_SECRET_TOKEN]';
    });

    return sanitized;
  }
}
```

### 2. `lib/core/observability/telemetry_service.dart` (Boundary Crash & Trace)

```dart
import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:sentry_flutter/sentry_flutter.dart';
import 'pii_masker.dart';

abstract interface class ITelemetryService {
  Future<void> recordError(
    Object exception,
    StackTrace? stackTrace, {
    String? contextMessage,
    bool fatal = false,
  });
  void addBreadcrumb(String message, String category);
  Future<void> setUserId(String? userId);
}

final class ProductionTelemetryService implements ITelemetryService {
  static final ProductionTelemetryService instance =
      ProductionTelemetryService._internal();

  ProductionTelemetryService._internal();

  @override
  Future<void> recordError(
    Object exception,
    StackTrace? stackTrace, {
    String? contextMessage,
    bool fatal = false,
  }) async {
    final maskedMessage = contextMessage != null
        ? PiiMasker.mask(contextMessage)
        : null;

    final sanitizedException = PiiMasker.mask(exception.toString());

    if (kReleaseMode) {
      await Sentry.captureException(
        sanitizedException,
        stackTrace: stackTrace,
        withScope: (scope) {
          if (maskedMessage != null) {
            scope.setContexts('ExecutionContext', {'message': maskedMessage});
          }
          if (fatal) {
            scope.level = SentryLevel.fatal;
          }
        },
      );
    } else {
      debugPrint('[TELEMETRY-LOCAL] Fatal: $fatal | Error: $sanitizedException');
      if (stackTrace != null) {
        debugPrint(stackTrace.toString());
      }
    }
  }

  @override
  void addBreadcrumb(String message, String category) {
    final sanitized = PiiMasker.mask(message);
    if (kReleaseMode) {
      Sentry.addBreadcrumb(
        Breadcrumb(
          message: sanitized,
          category: category,
          timestamp: DateTime.now().toUtc(),
        ),
      );
    } else {
      debugPrint('[BREADCRUMB] [$category]: $sanitized');
    }
  }

  @override
  Future<void> setUserId(String? userId) async {
    if (kReleaseMode) {
      // Hashing/Masking user id untuk regulasi GDPR/CCPA
      final maskedUser = userId != null
          ? SentryUser(id: PiiMasker.mask(userId))
          : null;
      await Sentry.configureScope((scope) => scope.setUser(maskedUser));
    }
  }
}
```

### 3. `lib/main.dart` (Bootstrapper Runtime Telemetri Bersih)

```dart
import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:sentry_flutter/sentry_flutter.dart';
import 'core/observability/telemetry_service.dart';

void main() {
  runZonedGuarded<Future<void>>(() async {
    WidgetsFlutterBinding.ensureInitialized();

    // 1. Tangkap sinkron Framework UI Error
    FlutterError.onError = (FlutterErrorDetails details) {
      FlutterError.presentError(details);
      ProductionTelemetryService.instance.recordError(
        details.exception,
        details.stack,
        contextMessage: 'FlutterError: ${details.context}',
        fatal: true,
      );
    };

    // 2. Tangkap asynchronous unhandled error pada Dart Root Isolate
    PlatformDispatcher.instance.onError = (Object error, StackTrace stack) {
      ProductionTelemetryService.instance.recordError(
        error,
        stack,
        contextMessage: 'PlatformDispatcher Root Isolate Uncaught Exception',
        fatal: true,
      );
      return true; // Return true menandakan error berhasil dicegah dari crash fatal OS
    };

    // 3. Inisialisasi Sentry Engine
    await SentryFlutter.init(
      (options) {
        options.dsn = const String.fromEnvironment('SENTRY_DSN');
        options.tracesSampleRate = 0.2; // 20% performance distributed sampling
        options.enableAutoPerformanceTracing = true;
        options.attachStacktrace = true;
        options.environment = const String.fromEnvironment(
          'APP_ENV',
          defaultValue: 'production',
        );
      },
      appRunner: () => runApp(const EnterpriseRootApp()),
    );
  }, (Object error, StackTrace stackTrace) {
    // 4. Tangkap seluruh Async errors yang lolos dari micro-task boundaries
    ProductionTelemetryService.instance.recordError(
      error,
      stackTrace,
      contextMessage: 'ZonedGuarded Fallback Boundary',
      fatal: true,
    );
  });
}

class EnterpriseRootApp extends StatelessWidget {
  const EnterpriseRootApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'FinTech Secure Core',
      home: Scaffold(
        appBar: AppBar(title: const Text('Production Observability')),
        body: const Center(
          child: Text('System Armed & Monitored.'),
        ),
      ),
    );
  }
}
```

### 4. `ios/fastlane/Fastfile` (Automated Build & TestFlight Deployment)

```ruby
default_platform(:ios)

platform :ios do
  before_all do
    ensure_git_status_clean
  end

  desc "Push candidate build to TestFlight securely using Match"
  lane :beta do |options|
    app_identifier = "com.fintech.securecore"
    
    # 1. Sinkronisasi Profile & Certificates via enkripsi Git (Zero-Trust)
    match(
      type: "appstore",
      storage_mode: "git",
      git_url: ENV["MATCH_GIT_URL"],
      readonly: is_ci,
      app_identifier: app_identifier
    )

    # 2. Increment Build Number otomatis berdasarkan timestamp CI / Git Run ID
    increment_build_number(
      build_number: ENV["GITHUB_RUN_NUMBER"] || Time.now.to_i.to_s,
      xcodeproj: "./Runner.xcodeproj"
    )

    # 3. Kompilasi Flutter binary via CLI dengan Obfuscation
    Dir.chdir("../..") do
      sh("flutter", "build", "ipa", "--release", 
         "--obfuscate", 
         "--split-debug-info=./ios-symbols")
    end

    # 4. Packaging dan Upload ke TestFlight
    upload_to_testflight(
      ipa: "../build/ios/ipa/Runner.ipa",
      skip_waiting_for_build_processing: true,
      api_key_path: ENV["APP_STORE_CONNECT_API_KEY_PATH"]
    )

    # 5. Notifikasi Observability: Upload dSYM files ke Sentry
    sentry_upload_dsym(
      auth_token: ENV["SENTRY_AUTH_TOKEN"],
      org_slug: "fintech-corp",
      project_slug: "flutter-ios",
      dsym_path: "./ios-symbols"
    )
  end
end
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter Arsitektur | Fastlane + Native Runners | CodeMagic / Bitrise (Hosted SaaS) | GitHub Actions Manual Bare-Metal |
| :--- | :--- | :--- | :--- |
| **Kontrol Eksekusi** | Penuh; runner dikonfigurasi sendiri (Self-hosted/Cloud). | Terbatas pada ekosistem UI vendor SaaS. | Penuh melalui runner virtual Linux/macOS VM. |
| **Kompleksitas Setup** | Tinggi; butuh setup Ruby runtime, Gems, & toolchains. | Sangat Rendah; out-of-the-box UI Flutter pre-installed. | Menengah; butuh deklarasi YAML pipeline presisi. |
| **Biaya Pemeliharaan** | Rendah secara lisensi, tapi tinggi pada maintenance engine. | Berbasis subscription bulanan berbiaya tinggi untuk skala besar. | Efisien secara biaya; memanfaatkan runner compute time per-menit. |
| **Isolasi Keamanan** | Terisolasi jika menggunakan ephemeral disposable VM. | Data melintasi infrastruktur vendor pihak ketiga (Security risk). | Terisolasi per container run; integrasi native OIDC tokens. |
| **Dukungan Obfuscation Mapping** | Manual via upload script custom. | Otomatis via plugin vendor. | Terintegrasi presisi melalui actions CLI tooling. |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. Zone Mismatch pada Platform Channels & Sentry SDK
*   *Failure Mode:* Jika library menginisialisasi event channel di luar zone aplikasi utama (contoh: di background isolate atau sebelum `runZonedGuarded`), error yang dilemparkan oleh library tersebut tidak akan pernah ditangkap oleh `ZonedGuarded` block. Hal ini memicu silent crash atau unhandled process termination di native layer tanpa jejak stack trace.
*   *Mitigasi:* Selalu pasang *safety net* ganda: `FlutterError.onError` dan `PlatformDispatcher.instance.onError`. Sejak rilis Flutter versi 3.3+, jangan hanya bergantung pada `runZonedGuarded`, melainkan delegasikan seluruh async uncaught error ke `PlatformDispatcher.onError`.

### 2. Kehilangan Mapping Simbol Obfuscation pada Multi-flavor Build
*   *Failure Mode:* Tim melakukan build flavor development, staging, dan production secara berurutan dalam runner yang sama. Eksekusi `flutter build` menimpa direktori simbol `--split-debug-info=./symbols`, sehingga tabel mapping yang diunggah ke Sentry adalah milik flavor staging, sementara binary rilis adalah production. Stack trace production menjadi mustahil didekripsi selamanya (*Garbled Unrecoverable Stack Trace*).
*   *Mitigasi:* Pisahkan path debug info secara dinamis menggunakan target environment dan commit hash, contoh:
    `--split-debug-info=./symbols/${BUILD_FLAVOR}/${GITHUB_SHA}`.

### 3. Out of Memory (OOM) Killer pada macOS CI Runner saat Kompilasi AOT
*   *Failure Mode:* Kompilasi Xcode dan Flutter AOT untuk arsitektur ARM64 memerlukan alokasi RAM besar (minimal 8GB - 16GB). Saat runner kehabisan memori, Linux kernel OOM Killer atau macOS system shutdown menghentikan proses tanpa memberikan pesan log yang jelas (hanya menghasilkan generic exit code 137).
*   *Mitigasi:* Batasi concurrency proses build dengan menyertakan argumen Xcode `-jobs 4` dan menonaktifkan heavy daemon:
    `flutter build ipa --dart-define=DartDevRollout=false`.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Hardcoding Credentials pada Flag `--dart-define`
*   *Kesalahan:* Memasukkan secret API key via terminal CI langsung: `--dart-define=API_KEY=supersecret123`. Nilai ini tersimpan dalam cleartext di log CI, serta terkompilasi langsung ke dalam static binary string table yang mudah diekstraksi menggunakan perintah `strings libapp.so`.
*   *Solusi:* Gunakan backend-for-frontend (BFF) pattern atau ambil dynamic tokens via runtime secure storage/vault setelah handshaking SSL pinning, bukan membakar static production credentials ke dalam biner.

### 2. Lupa Mengunggah Mapping R8/ProGuard Bersamaan dengan Dart Symbols
*   *Kesalahan:* Developer hanya mengunggah file `.symbols` milik Dart ke crash reporting dashboard, namun melupakan file `mapping.txt` milik R8 (terletak di `android/app/build/outputs/mapping/release/mapping.txt`).
*   *Akibat:* Ketika crash terjadi di layer Android native bridge (contoh: Java/Kotlin plugin integration), stack trace menampilkan baris native yang terobfuscasi (`a.b.c.method()`) sehingga akar masalah tidak dapat dianalisis.
*   *Solusi:* Konfigurasikan gradle build task