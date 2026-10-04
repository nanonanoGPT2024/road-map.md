# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 05: Asynchronous, Concurrency, Network, dan API Layer**
**Kategori: 03-Frontend-and-Mobile (Flutter)**

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, engineer diharapkan mampu:
1. **Menganalisis dan Memanipulasi Concurrency Engine Dart**: Memahami siklus internal *Event Loop*, memprioritaskan tugas di *Microtask Queue* vs *Event Queue*, dan mengeliminasi *UI thread jank* dengan arsitektur multi-isolate (*Isolate Groups*, zero-copy pointer pass, worker pools).
2. **Merancang Network Layer Kelas Enterprise**: Membangun client abstraction berbasis Dio yang modular, decouple, *testable*, dan memenuhi prinsip Clean Architecture.
3. **Mengimplementasikan Robust Token Refresh Pipeline**: Mencegah *race condition* autentikasi menggunakan *queued interceptors* dan *synchronization primitives* (Mutex/Lock) saat terjadi multiple concurrent requests pada token kedaluwarsa.
4. **Menerapkan Zero-Trust Security pada Layer Transport**: Mengonfigurasi *SSL/TLS Certificate Pinning* dan *Public Key (SPKI) Pinning* menggunakan native network hooks guna mencegah serangan Man-In-The-Middle (MITM).
5. **Membangun Resilience & Parsing Engine**: Mengimplementasikan *Circuit Breaker pattern*, *Exponential Backoff with Full Jitter*, serta *background isolate deserialization pipeline* untuk payload JSON berukuran masif (megabytes).

---

## 2. Prerequisite

Sebelum mempelajari modul ini, pastikan Anda telah menguasai:
* Pemahaman fundamental `Future`, `Stream`, dan sintaks `async`/`await` pada Dart 3.x.
* Konsep transport layer HTTP/1.1, HTTP/2, RESTful constraints, serta status code standar RFC 9110.
* Dasar arsitektur perangkat lunak: Separation of Concerns (SoC), Dependency Injection (DI), dan Clean Architecture.
* Pemahaman dasar tentang asymmetric encryption, sertifikat X.509, dan SHA-256 fingerprinting.

---

## 3. Concept & Internal Architecture

### 3.1 Dart Concurrency Model: Event Loop, Microtasks, dan Isolate Groups

Berbeda dengan runtime multi-threaded berbasis shared-memory (seperti Java Virtual Machine atau CLR pada .NET), Dart secara historis beroperasi dalam model **shared-nothing actor concurrency**. Setiap unit eksekusi terisolasi disebut **Isolate**.

```
+-------------------------------------------------------------------------+
|                              ISOLATE                                    |
|                                                                         |
|  +--------------------+         +------------------------------------+  |
|  |    Isolate Heap    |         |             Call Stack             |  |
|  | (Allocated Memory) |         |                                    |  |
|  +--------------------+         +------------------------------------+  |
|                                                    ^                    |
|                                                    | (Pushes frame)     |
|                 +----------------------------------+                    |
|                 |                                                       |
|  +-----------------------------+                                        |
|  |         EVENT LOOP          |                                        |
|  +-----------------------------+                                        |
|         ^               ^                                               |
|         | (Drain first) | (Drain if Microtask Empty)                    |
|  +---------------+     +---------------+                                |
|  | Microtask     |     | Event         |                                |
|  | Queue         |     | Queue         |                                |
|  +---------------+     +---------------+                                |
|  - scheduleMicrotask   - I/O Events (Network, Disk)                     |
|  - Future.microtask    - User Input (Gestures)                          |
|                        - Timer (Timer.run)                              |
|                        - Isolate Ports Message                          |
+-------------------------------------------------------------------------+
```

#### Event Loop Lifecycle
Event loop bekerja dalam siklus tak terhingga dengan aturan strict priority:
1. **Microtask Queue Prioritization**: Event Loop akan memeriksa dan mengeksekusi seluruh antrean `Microtask Queue` hingga kosong secara absolut (FIFO) sebelum memproses satu pun item dari `Event Queue`.
2. **Microtask Starvation Warning**: Jika microtask menjadwalkan microtask baru secara rekursif, event loop tidak akan pernah berpindah ke `Event Queue`, menyebabkan UI membeku (*frame drop/freeze*) dan event I/O terhenti.
3. **Event Queue Execution**: Mengambil satu event dari `Event Queue`, memprosesnya ke Call Stack hingga tuntas, lalu segera kembali memeriksa `Microtask Queue`.

#### Isolate Groups (Dart 2.15+)
Pada versi modern Dart, Isolates yang di-spawn dari root isolate yang sama berada di dalam satu **Isolate Group**. 
* Isolate-isolate ini berbagi program structure yang sama (classes, compiled code) dan GC heap management yang terkonsolidasi.
* Spawn cost terpangkas hingga 100x lipat lebih cepat dengan konsumsi memori footprint ~10-30 KB vs ~2 MB pada legacy isolate.
* **Zero-copy sharing**: Nilai immutable tertentu, payload biner berukuran masif (`TransferableTypedData`), atau objek unmodifiable dapat ditransfer antar-isolate tanpa overhead deep-copy serialisasi.

---

### 3.2 Enterprise Network Layer Engine (Dio Core Mechanics)

Di balik abstraction layer Dio, arsitektur request-response pipeline dipecah menjadi pipeline interceptor deterministik:

```
[Request Initiation] 
        │
        ▼
[Dio.interceptors.onRequest] ──► (Inject Token, Signature HMAC, Device Headers)
        │
        ▼
[HttpClientAdapter] ───────────► Engine-level socket dispatch (dart:io / Cronet)
        │                         │  ▲
        │                         │  │ Handshake via SecurityContext (SSL Pinning)
        ▼                         ▼  │
[Remote Server / Gateway] ◄──────────┘
        │
        ▼
[HttpClientAdapter Response]
        │
        ▼
[Dio.interceptors.onResponse] ──► (Decryption, Metrics logging, Local Caching)
   - OR -
[Dio.interceptors.onError] ────► (401 Interception, Queued Mutex Refresh, Retry)
        │
        ▼
[Caller Repository / UI]
```

#### The 401 Unauthorized Concurrency Problem
Ketika user mengakses aplikasi, UI sering kali memicu banyak network requests secara simultan (misal: fetching profile, dashboard cards, unread notifications). Jika `access_token` telah kedaluwarsa pada saat itu, semua endpoint akan mengembalikan status `401 Unauthorized` dalam rentang milidetik yang sama.

Jika ditangani secara naif:
* Server menerima `N` request refresh token secara simultan.
* Refresh token rotation akan meng-invalida token pada hit pertama, menyebabkan `N-1` request refresh lainnya gagal dengan error `Invalid Grant/Refresh Token Expired`.
* User secara paksa di-logout secara mendadak.

Solusinya adalah mengunci (*locking*) alur refresh menggunakan `QueuedInterceptor` pada Dio, menunda semua request yang gagal, mengeksekusi *single refresh token request*, memperbarui token store, dan me-replay seluruh request yang tertunda secara transparan.

---

## 4. Why & What

| Dimensi | Pendekatan Dasar (`http.get` / Default Dio) | Enterprise Network Architecture |
| :--- | :--- | :--- |
| **JSON Deserialization** | Dieksekusi pada UI isolate (Event loop utama). Payload >2MB memicu frame drop (jank). | Didelegasikan ke background worker isolates via lightweight workers atau `Isolate.run`. |
| **Token Expiry Handling** | Request gagal langsung diteruskan ke UI layer; user terlempar ke login screen. | Ditangani transparan di transport layer melalui Mutex-locked QueuedInterceptors. |
| **Security & Transport** | Mempercayai seluruh Root CA di operating system secara default (rawan MITM proxy). | Certificate Pinning / SPKI SHA-256 Public Key Pinning dengan fallback fail-closed. |
| **Fault Tolerance** | Gagal total saat jaringan berfluktuasi atau server mengalami lonjakan beban. | Circuit Breaker & Exponential Backoff dengan Full Jitter algorithm. |
| **Maintainability** | URL hardcoded, parsing logika tercampur di UI State Controller. | Domain Entities decoupled dari Data Transfer Objects (DTO) dengan explicit mappers. |

---

## 5. How (Workflow Detail)

### 5.1 End-to-End Concurrent 401 Handling & Token Re-play Workflow
1. Request $R_1, R_2, R_3$ dikirim secara simultan.
2. Server merespons ketiganya dengan status `401 Unauthorized`.
3. Interceptor menangkap response $R_1$:
   - Memeriksa flag status refresh (Mutex lock). Karena belum terkunci, set `isRefreshing = true`.
   - Menahan request $R_1$ ke dalam holding queue.
4. Interceptor menangkap response $R_2$ dan $R_3$:
   - Menyadari bahwa `isRefreshing == true`.
   - Memasukkan request $R_2$ dan $R_3$ langsung ke antrean holding queue tanpa memicu call refresh baru.
5. Client mengirim single payload `POST /v1/auth/refresh` ke Identity Provider.
6. Respons `200 OK` diterima dengan sepasang token baru: `New_Access_Token` dan `New_Refresh_Token`.
7. Client memperbarui persistent storage (misal: Flutter Secure Storage).
8. Mengubah header authorization pada $R_1, R_2, R_3$ dengan `New_Access_Token`.
9. Re-dispatch $R_1, R_2, R_3$ ke network adapter melalui `dio.fetch()`.
10. Melepaskan lock `isRefreshing = false`. UI menerima payload data tanpa pernah mengetahui terjadi kedaluwarsa token.

---

## 6. Analogy & Diagram ASCII

### Analogi: Konferensi Diplomatik Internasional
* **UI Isolate**: Duta Besar yang sedang berpidato di podium. Dia tidak boleh diganggu atau diinterupsi oleh hal-hal lambat (jank), agar pidato berjalan mulus.
* **Worker Isolate**: Staf intelijen dan penerjemah di ruang bawah tanah. Mereka menerima tumpukan dokumen rahasia terenkripsi (JSON Payload 10MB), mendekripsinya, menganalisisnya, lalu hanya menyerahkan selembar kesimpulan bersih (Domain Entities) ke Duta Besar.
* **Token Mutex Interceptor**: Paspor diplomatik Duta Besar kedaluwarsa saat 3 ajudan hendak memasuki gerbang perbatasan secara bersamaan. Alih-alih 3 ajudan berlari bersamaan ke kedutaan untuk memperpanjang paspor, hanya 1 ajudan yang pergi mengurus perpanjangan; 2 ajudan lainnya duduk tertib menunggu di pos perbatasan. Begitu paspor baru tiba, ketiganya melenggang masuk.

### Diagram: Alur Eksekusi Queued Token Refresh

```
CLIENT ENGINE (DIO)                     SECURITY GATEWAY / BACKEND
       │                                            │
       ├─── Request A (Token Expired) ─────────────►│
       ├─── Request B (Token Expired) ─────────────►│
       │                                            │
       │◄── 401 Unauthorized (Response A) ──────────┤
       │                                            │
 [ACQUIRE LOCK]                                     │
   - Queue Request A                                │
   - Lock State: isRefreshing = true                │
       │                                            │
       │◄── 401 Unauthorized (Response B) ──────────┤
   - Detect isRefreshing == true                    │
   - Queue Request B                                │
       │                                            │
       ├─── POST /v1/auth/refresh ─────────────────►│
       │                                            │
       │◄── 200 OK (New Access & Refresh Tokens) ───┤
       │                                            │
 [UPDATE SECURE STORAGE]                            │
 [REPLAY QUEUED REQUESTS]                           │
       ├─── Request A (New Token) ─────────────────►│
       ├─── Request B (New Token) ─────────────────►│
       │                                            │
 [RELEASE LOCK]                                     │
   - Lock State: isRefreshing = false               │
       │                                            │
       │◄── 200 OK (Payload Data A) ────────────────┤
       │◄── 200 OK (Payload Data B) ────────────────┤
```

---

## 7. Implementation: Simple vs Enterprise Code

### 7.1 Simple Example: Background Isolate Parsing
Menggunakan utilitas modern `Isolate.run` untuk memindahkan komputasi deserialization JSON di luar UI thread.

```dart
import 'dart:convert';
import 'package:flutter/foundation.dart';

class LedgerItem {
  final String id;
  final double amount;

  LedgerItem({required this.id, required this.amount});

  factory LedgerItem.fromJson(Map<String, dynamic> json) {
    return LedgerItem(
      id: json['id'] as String,
      amount: (json['amount'] as num).toDouble(),
    );
  }
}

// Top-level or static function for Isolate execution
List<LedgerItem> parseLedgerPayload(String rawJson) {
  final decoded = jsonDecode(rawJson) as List<dynamic>;
  return decoded
      .map((item) => LedgerItem.fromJson(item as Map<String, dynamic>))
      .toList();
}

class LedgerParserService {
  Future<List<LedgerItem>> parseLargeJson(String rawJson) async {
    // Isolate.run spawns, executes, and closes the isolate automatically
    return await Isolate.run(() => parseLedgerPayload(rawJson));
  }
}
```

---

### 7.2 Practical Example: Enterprise Network Stack

Di bawah ini adalah implementasi lengkap mencakup:
1. `QueuedInterceptor` untuk handling concurrency 401 dengan token refresh.
2. Custom `HttpClientAdapter` untuk enforce SHA-256 Public Key Pinning (SPKI Pinning).

```dart
import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:crypto/crypto.dart';
import 'package:dio/dio.dart';
import 'package:dio/io.dart';

// ---------------------------------------------------------------------------
// 1. SECURE TOKEN STORAGE ABSTRACTION
// ---------------------------------------------------------------------------
abstract class ITokenRepository {
  Future<String?> getAccessToken();
  Future<String?> getRefreshToken();
  Future<void> saveTokens({required String accessToken, required String refreshToken});
  Future<void> clearTokens();
}

// ---------------------------------------------------------------------------
// 2. CONCURRENT-SAFE AUTH QUEUED INTERCEPTOR
// ---------------------------------------------------------------------------
class EnterpriseAuthInterceptor extends QueuedInterceptor {
  final ITokenRepository _tokenRepository;
  final Dio _refreshDio;

  EnterpriseAuthInterceptor({
    required ITokenRepository tokenRepository,
    required Dio refreshDio,
  })  : _tokenRepository = tokenRepository,
        _refreshDio = refreshDio;

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    final token = await _tokenRepository.getAccessToken();
    if (token != null && token.isNotEmpty) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    // Intercept only 401 Unauthorized
    if (err.response?.statusCode != 401) {
      return handler.next(err);
    }

    // Hindari infinite loop jika request refresh-token itu sendiri yang 401
    if (err.requestOptions.path.contains('/v1/auth/refresh')) {
      await _tokenRepository.clearTokens();
      return handler.next(err);
    }

    try {
      final currentRefreshToken = await _tokenRepository.getRefreshToken();
      if (currentRefreshToken == null || currentRefreshToken.isEmpty) {
        throw DioException(
          requestOptions: err.requestOptions,
          error: 'No refresh token available',
        );
      }

      // Lakukan call refresh menggunakan client terpisah agar tidak intercepted
      final refreshResponse = await _refreshDio.post(
        '/v1/auth/refresh',
        data: {'refresh_token': currentRefreshToken},
      );

      final newAccessToken = refreshResponse.data['access_token'] as String;
      final newRefreshToken = refreshResponse.data['refresh_token'] as String;

      await _tokenRepository.saveTokens(
        accessToken: newAccessToken,
        refreshToken: newRefreshToken,
      );

      // Replay request awal yang gagal dengan access token baru
      final options = err.requestOptions;
      options.headers['Authorization'] = 'Bearer $newAccessToken';

      final response = await _refreshDio.fetch(options);
      return handler.resolve(response);
    } catch (refreshError) {
      await _tokenRepository.clearTokens();
      return handler.reject(
        DioException(
          requestOptions: err.requestOptions,
          error: 'Session Expired. User must re-authenticate: $refreshError',
        ),
      );
    }
  }
}

// ---------------------------------------------------------------------------
// 3. HARDENED SSL/TLS PINNING CLIENT ADAPTER (Native dart:io)
// ---------------------------------------------------------------------------
class SslPinningAdapterFactory {
  /// Memvalidasi sertifikat SHA-256 fingerprint terhadap remote server.
  static IOHttpClientAdapter create({
    required Set<String> allowedSha256Fingerprints,
  }) {
    final adapter = IOHttpClientAdapter();

    adapter.createHttpClient = () {
      final securityContext = SecurityContext(withTrustedRoots: false);
      final client = HttpClient(context: securityContext);

      // Timeout untuk socket level establishment
      client.connectionTimeout = const Duration(seconds: 10);

      client.badCertificateCallback = (
        X509Certificate cert,
        String host,
        int port,
      ) {
        // Ekstraksi binary DER dari remote leaf certificate
        final List<int> derCert = cert.der;
        final String certSha256 = sha256.convert(derCert).toString().toUpperCase();

        final bool isPinned = allowedSha256Fingerprints
            .map((fp) => fp.replaceAll(':', '').toUpperCase())
            .contains(certSha256);

        if (!isPinned) {
          // Trigger alert/audit log ke platform logging internal
          stderr.writeln(
            'CRITICAL SECURITY ALERT: Pinning mismatch for $host. Untrusted: $certSha256',
          );
        }

        // Return true HANYA jika hash cocok persis
        return isPinned;
      };

      return client;
    };

    return adapter;
  }
}
```

---

## 8. Real World Case Study: High-Frequency FinTech App

### Konteks
Aplikasi Neobank Enterprise dengan 3 juta active user. Ketika pengguna membuka layar portofolio:
* Terjadi pemanggilan 12 endpoint API secara paralel via `Future.wait`.
* Payload endpoint `/v1/portfolio/ledger` berisi rekonsiliasi transaksi sebesar ~4.8 MB format JSON mentah.
* Backend Identity Server menggunakan token expiration time yang sangat agresif (5 menit) demi standar compliance PSD2.

### Masalah Produksi (Incident)
1. **Severe UI Jank**: UI membeku rata-rata 380 ms hingga 500 ms saat decoding JSON ledger di layar utama, merusak animasi balance counter (drop ke 0 FPS).
2. **Session Desynchronization Cascading Failure**: Di saat access token kedaluwarsa, 12 parallel requests serentak mengirim 12 token refresh request. Akibat implementasi token rotation di server, 1 request berhasil, 11 request lain dianggap *token replay attack*, sehingga akun pengguna di-freeze sementara secara otomatis oleh security gateway.
3. **MITM Susceptibility**: Audit security menemukan potensi interception pada internal enterprise proxy yang diinstal oleh software monitoring di perangkat corporate.

### Solusi Arsitektural
1. **Isolated Deserializer**: Membuat dedicated static transformer yang mem-parsing decoding model menggunakan `Isolate.run`, membebaskan main isolate dari parsing 4.8 MB JSON string.
2. **Atomic Interceptor Lock**: Mengubah interceptor standar ke `QueuedInterceptor`, memastikan single-flight execution untuk token rotation.
3. **SPKI Pinning**: Menerapkan dynamic pin validation pada transport adapter, me-reject sertifikat root lokal yang tidak terdaftar.

### Hasil Metrik (Before vs After)

| Metrik Kinerja | Sebelum Implementasi | Sesudah Implementasi |
| :--- | :--- | :--- |
| **Main Thread Frame Jank** | 420 ms (Rata-rata) | 1.8 ms (Bebas Jank) |
| **UI Rendering Rate** | 12 - 24 FPS (Stutter) | Konsisten 60/120 FPS |
| **False-Positive Account Locks** | 8.4% harian | 0.00% |
| **Token Refresh Network Calls** | 12 calls per session drop | Tepat 1 call terisolasi |

---

## 9. Trade-offs & Engineering Decisions

```
                           [SECURITY/ROBUSTNESS]
                                   ▲
                                   │   * Enterprise Network Stack
                                   │     (SPKI Pinning, Full Jitter,
                                   │      Queued Interceptors, Background Isolates)
                                   │
                                   │
                                   │
                                   │   * Default Dio Setup
                                   │     (Basic Interceptor, In-thread Parsing)
                                   │
                                   │   * Basic http.get
                                   │
                                   └─────────────────────────────► [SIMPLICITY / DEV VELOCITY]
```

### Matriks Trade-off

| Parameter | Pendekatan Terisolasi & Terpinning | Pendekatan Langsung / Sederhana |
| :--- | :--- | :--- |
| **CPU & Battery Consumption** | Lebih efisien pada UI rendering, tetapi ada overhead minimal saat spawning isolates. | Mengonsumsi CPU langsung di main thread. Menguras daya saat jank terjadi berulang. |
| **Latency Network** | Bertambah ~5-15 ms saat antrean interceptor me-route serial refresh call. | 0 ms interceptor overhead, tetapi langsung gagal jika token invalid. |
| **Maintenance Burden** | Tinggi: Sertifikat kedaluwarsa mengharuskan app update atau backend-driven dynamic pin synchronization. | Rendah: Mengandalkan CA bawaan OS secara otomatis. |
| **Architectural Complexity** | Tinggi: Mengimplementasikan clean failure domains, retry policies, thread dispatching. | Rendah: Menulis langsung logic di screen-level controller. |

---

## 10. Common Mistakes & Troubleshooting

### 1. The Isolate Passing Trap (Closure Serialization Failure)
* **Gejala**: Error runtime `ArgumentError: Invalid argument: closure cannot be sent to an isolate`.
* **Akar Masalah**: Mencoba memanggil method non-static atau anonymous function yang me-reference state instance (`this`) dari kelas luar ke dalam `Isolate.run` atau `compute`.
* **Solusi**: Gunakan top-level function murni atau `static method` yang sepenuhnya decoupled dari instance variables.

### 2. Microtask Loop Starvation
* **Gejala**: Animasi Flutter (seperti `CircularProgressIndicator`) berhenti total tanpa memicu Crash Log, gesture tap tidak merespons.
* **Akar Masalah**: Developer menggunakan recursive chaining `scheduleMicrotask()` atau loop tak terhingga di Microtask queue yang menyerap habis siklus Event Loop.
* **Solusi**: Pindahkan tugas komputasi berat ke `Isolate` atau pecah dengan penundaan `Future.delayed(Duration.zero)`.

### 3. Pinning Brick (The Expired Cert Disaster)
* **Gejala**: Seluruh pengguna tidak bisa mengakses backend setelah tim infrastructure melakukan rotasi sertifikat domain tahunan.
* **Akar Masalah**: Hardcoded certificate hash tanpa back-up hash (cold backup key) di aplikasi klien.
* **Solusi**: Terapkan **Backup Pins** (minimal 2 public key hash cadangan: primary cert, intermediate cert, dan backup key offline yang aman).

---

## 11. Best Practices & Production Checklist

- [ ] **Configurable Timeouts**: Selalu definisikan eksplisit `connectTimeout`, `receiveTimeout`, dan `sendTimeout` (Rekomendasi: `15000ms` untuk standard API, jangan pernah set `0` / infinity).
- [ ] **SPKI Over Full Certificate Pinning**: Pin Public Key (SPKI) alih-alih seluruh sertifikat leaf, sehingga pembaruan sertifikat dengan Common Name & Keypair yang sama tidak merusak aplikasi (*anti-bricking*).
- [ ] **Decouple Data Models**: Jangan ekspos Dio `Response` atau DTO beranotasi serialization ke domain/UI layer. Map secara eksplisit ke pure immutable Domain Entities.
- [ ] **Idempotency Keys**: Selalu sertakan header `X-Idempotency-Key` (UUIDv4) pada operasi `POST`/`PATCH` non-idempoten untuk mencegah double processing saat transport level retry terjadi.
- [ ] **Exponential Backoff with Full Jitter**: Hindari synchronized burst retry yang dapat menyebabkan distributed thundering herd problem ke backend. Rumus jitter:
  $$T_{\text{sleep}} = \text{random}(0, \min(T_{\text{max}}, T_{\text{base}} \times 2^{\text{attempt}}))$$

---

## 12. Hands-on Practice

Buatlah struktur proyek lokal Anda mengikuti panduan enterprise berikut:

```
hands-on/m02/
├── lib/
│   ├── core/
│   │   ├── network/
│   │   │   ├── dio_client.dart
│   │   │   ├── interceptors/
│   │   │   │   ├── auth_interceptor.dart
│   │   │   │   └── retry_interceptor.dart
│   │   │   └── parser/
│   │   │       └── background_parser.dart
│   │   └── security/
│   │       └── ssl_pinning_adapter.dart
│   └── main.dart
└── test/
    └── network_test.dart
```

### Langkah Praktikum:

#### Langkah 1: Buat Background Worker Deserializer
Buat file `lib/core/network/parser/background_parser.dart`:

```dart
import 'dart:convert';
import 'package:flutter/foundation.dart';

typedef ItemFactory<T> = T Function(Map<String, dynamic> json);

class BackgroundParser {
  static Future<List<T>> parseList<T>({
    required String rawJson,
    required ItemFactory<T> factory,
  }) async {
    return compute(_isolateListParse, _ListPayload(rawJson, factory));
  }

  static List<T> _isolateListParse<T>(_ListPayload<T> payload) {
    final decoded = jsonDecode(payload.rawJson) as List<dynamic>;
    return decoded
        .cast<Map<String, dynamic>>()
        .map(payload.factory)
        .toList();
  }
}

class _ListPayload<T> {
  final String rawJson;
  final ItemFactory<T> factory;

  _ListPayload(this.rawJson, this.factory);
}
```

#### Langkah 2: Buat Resilient Retry Interceptor dengan Full Jitter
Buat file `lib/core/network/interceptors/retry_interceptor.dart`:

```dart
import 'dart:math';
import 'package:dio/dio.dart';

class FullJitterRetryInterceptor extends Interceptor {
  final Dio dio;
  final int maxRetries;
  final int baseDelayMs;
  final int maxDelayMs;
  final Random _random = Random();

  FullJitterRetryInterceptor({
    required this.dio,
    this.maxRetries = 3,
    this.baseDelayMs = 500,
    this.maxDelayMs = 5000,
  });

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    final requestOptions = err.requestOptions;
    int retryCount = requestOptions.extra['retryCount'] ?? 0;

    if (_shouldRetry(err) && retryCount < maxRetries) {
      retryCount++;
      requestOptions.extra['retryCount'] = retryCount;

      // Calculate Full Jitter Backoff
      final int expDelay = baseDelayMs * pow(2, retryCount - 1).toInt();
      final int calculatedMax = min(expDelay, maxDelayMs);
      final int jitterDelay = _random.nextInt(calculatedMax + 1);

      await Future.delayed(Duration(milliseconds: jitterDelay));

      try {
        final response = await dio.fetch(requestOptions);
        return handler.resolve(response);
      } catch (e) {
        return super.onError(err, handler);
      }
    }

    return super.onError(err, handler);
  }

  bool _shouldRetry(DioException err) {
    // Retry on transport failures or 5xx server issues
    return err.type == DioExceptionType.connectionTimeout ||
        err.type == DioExceptionType.sendTimeout ||
        err.type == DioExceptionType.receiveTimeout ||
        (err.response != null &&
            err.response!.statusCode != null &&
            err.response!.statusCode! >= 500 &&
            err.response!.statusCode! <= 599);
  }
}
```

---

## 13. Exercise

### Level Easy
Modifikasi `FullJitterRetryInterceptor` agar tidak pernah mengulang request HTTP metode `POST` kecuali endpoint tersebut secara eksplisit memiliki flag `extra: {'isIdempotent': true}`.

### Level Medium
Implementasikan memory-caching layer di dalam interceptor:
* Mengembalikan respons instan dari RAM jika request endpoint `GET` sama pernah dipanggil dalam 60 detik terakhir.
* Tambahkan invalidation logic: bersihkan cache saat endpoint yang mengubah data dipanggil (`POST`, `PUT`, `DELETE`).

### Level Hard
Bangun implementasi **Sliding-Window Circuit Breaker Interceptor** untuk Dio dari awal:
* Simpan status request ke dalam window geser berukuran 20 request terakhir.
* Jika rasio kegagalan (status 5xx atau Timeout) melampaui ambang batas 50%, transisikan state dari `Closed` ke `Open`.
* Tolak request baru secara fail-fast selama 30 detik tanpa melakukan transport dispatch (`CircuitBreakerOpenException`).
* Setelah 30 detik, ubah state menjadi `Half-Open` untuk mengizinkan satu probe request. Jika sukses, kembalikan ke `Closed`; jika gagal, reset cooldown.

---

## 14. Challenge: Offline-First Mutation Synchronization Engine

### Skenario & Persyaratan
Rancang dan bangun arsitektur sistem offline-first untuk modul transaksi kasir (Point-Of-Sale):
1. **Queued Mutations**: Transaksi saat jaringan terputus harus disimpan ke dalam local persistent storage (misal: SQLite/Isar) dengan UUID v4 idempotency token.
2. **Deterministic Sequence Pipeline**: Ketika perangkat kembali terhubung ke internet, mutasi harus dieksekusi secara serial sesuai urutan pembuatan awal (*FIFO*).
3. **Conflict Resolution Architecture**: Jika server mendeteksi konflik pada inventory stock (status HTTP `409 Conflict`), implementasikan sistem rekonsiliasi yang mengeksekusi *Server-Managed Rollback* dan mengembalikan status penyesuaian ke layar tanpa merusak antrean lokal selanjutnya.
4. **Isolate Guard**: Proses serialisasi data mutasi dan update database lokal masif tidak boleh memicu frame drop pada animasi antarmuka kasir.

---

## 15. Quiz Evaluasi Pemahaman

### Bagian 1: Basic (5 Soal)
1. **Apa perbedaan prioritas eksekusi antara Microtask Queue dan Event Queue dalam siklus event loop Dart?**
   - *A.* Event Queue selalu dieksekusi lebih dulu daripada Microtask Queue.
   - *B.* Microtask Queue dieksekusi hingga habis sebelum event berikutnya dari Event Queue diproses.
   - *C.* Keduanya dieksekusi secara acak tergantung ketersediaan thread CPU.
   - *D.* Event Queue hanya menangani timer, sedangkan Microtask menangani seluruh HTTP request.

2. **Mengapa `compute()` atau `Isolate.run()` lebih disukai untuk parsing JSON berukuran masif dibandingkan parsing langsung di dalam method async UI Controller?**
   - *A.* Karena `jsonDecode` tidak bisa berjalan di main thread secara sintaksis.
   - *B.* Parsing JSON di main thread memblokir event loop dan menyebabkan UI jank/frame drop.
   - *C.* Background Isolate membuat koneksi HTTP berjalan lebih cepat.
   - *D.* `Isolate.run` otomatis mengenkripsi payload JSON.

3. **Status kode HTTP manakah yang menjadi trigger standar untuk alur token refresh?**
   - *A.* 400 Bad Request
   - *B.* 403 Forbidden
   - *C.* 401 Unauthorized
   - *D.* 502 Bad Gateway

4. **Dalam konteks Dart Isolates modern (Dart 2.15+), apa yang dimaksud dengan Isolate Group?**
   - *A.* Sekumpulan isolate yang membagi stack eksekusi secara paralel pada CPU core tunggal.
   - *B.* Isolate yang berbagi core memory structure/code dan GC yang sama untuk spawn time dan memory footprint yang jauh lebih efisien.
   - *C.* Mekanisme isolate legacy yang mengandalkan shared memory tanpa port passing.
   - *D.* Struktur data untuk mengelompokkan Future ke dalam microtask.

5. **Apa fungsi utama dari `badCertificateCallback` pada class `HttpClient` di Dart?**
   - *A.* Mengabaikan seluruh error SSL tanpa syarat di lingkungan produksi.
   - *B.* Menginterupsi handshake TLS untuk memeriksa validitas fingerprint sertifikat terhadap hash yang diizinkan (SSL Pinning).
   - *C.* Memperbaiki sertifikat yang rusak secara otomatis dari client.
   - *D.* Mengubah protocol transport dari HTTPS ke HTTP.

---

### Bagian 2: Intermediate (5 Soal)
6. **Apa bahaya teknis dari penggunaan `scheduleMicrotask` secara berulang-ulang tanpa mekanisme terminasi yang ketat?**
   - *A.* Terjadi Out of Memory (OOM) secara instan dalam 1 detik.
   - *B.* Terjadi *Microtask Starvation*, di mana Event Queue tidak pernah diproses, membuat UI dan I/O freeze.
   - *C.* Aplikasi otomatis melakukan switch context ke Isolate baru.
   - *D.* Dio client otomatis membatalkan seluruh request yang berjalan.

7. **Mengapa standar enterprise merekomendasikan `QueuedInterceptor` daripada `Interceptor` standar pada Dio saat menangani refresh token?**
   - *A.* `QueuedInterceptor` memproses request di background thread yang terpisah.
   - *B.* `QueuedInterceptor` mengantrekan request/response/error secara sequential, mencegah race condition pada simultaneous token refreshes.
   - *C.* `QueuedInterceptor` otomatis mengimplementasikan caching.
   - *D.* `Interceptor` standar tidak mendukung method `onError`.

8. **Apa keunggulan SPKI (Subject Public Key Info) SHA-256 Pinning dibandingkan Certificate Leaf Pinning?**
   - *A.* SPKI tidak membutuhkan hashing cryptographic.
   - *B.* Aplikasi tidak akan rusak (*brick*) saat sertifikat dirotasi, selama Key Pair publik yang digunakan tetap sama.
   - *C.* SPKI pinning dapat memverifikasi seluruh domain tanpa registrasi.
   - *D.* SPKI menghilangkan kebutuhan TLS handshake.

9. **Apa tujuan penambahan parameter "Jitter" pada algoritma Exponential Backoff saat melakukan retry network request?**
   - *A.* Memaksa request menggunakan HTTP/2 protocol.
   - *B.* Mengurangi payload size secara dinamis saat retry.
   - *C.* Menghindari *Thundering Herd Problem* dengan memecah gelombang collision retry serentak dari banyak client.
   - *D.* Memastikan paket data dikirim melalui jalur routing terpendek.

10. **Batasan utama dari data yang dapat dikirimkan melalui message passing (`SendPort`/`ReceivePort`) antar-isolate adalah:**
    - *A.* Tidak dapat mengirimkan tipe data primitif seperti `int` atau `String`.
    - *B.* Tidak dapat mengirimkan object yang terikat native resources, live socket, atau closure dengan mutable external references.
    - *C.* Data dibatasi maksimal sebesar 64 KB saja.
    - *D.* Seluruh data harus diubah menjadi format Base64 terlebih dahulu.

---

### Bagian 3: Enterprise Case Scenarios (3 Soal)

11. **Skenario Kasus 1**: Tim SRE Anda melaporkan lonjakan tajam error `503 Service Unavailable` selama jam sibuk. Investigasi menunjukkan bahwa saat jaringan internet publik mengalami fluktuasi sesaat, 50.000 aplikasi mobile secara agresif melakukan retry simultan tepat setiap 1000ms tanpa penundaan acak. Arsitektur mitigasi apa yang paling tepat diimplementasikan pada network client mobile?
    - *A.* Hentikan seluruh mekanisme retry dan tampilkan error langsung ke pengguna.
    - *B.* Terapkan Exponential Backoff dengan Full Jitter dan batasi retry maksimal 3 kali, dengan status verifikasi idempotency.
    - *C.* Ganti transport network dari HTTPS ke raw TCP socket.
    - *D.* Ubah konfigurasi Dio timeout menjadi 1 milidetik agar fail-fast instan.

12. **Skenario Kasus 2**: Sebuah aplikasi perbankan mengalami freeze selama 1.2 detik saat melakukan decrypt dan mapping data 10.000 riwayat transaksi rekening koran. Pengujian profiler menunjukkan garbage collector bekerja keras di main thread. Bagaimana solusi rekayasa terbaik untuk kasus ini?
    - *A.* Pecah payload menjadi beberapa Future microtask di UI thread.
    - *B.* Bungkus proses deserialization dan instansiasi entity di dalam worker isolate via `Isolate.run`, dan transfer hasilnya ke UI layer.
    - *C.* Tingkatkan frame budget Flutter dengan mematikan widget rebuild logging.
    - *D.* Ubah JSON format menjadi XML.

13. **Skenario Kasus 3**: Tim QA menemukan celah di mana saat koneksi proxy disusupi sertifikat Burp Suite/Charles Proxy buatan internal pada perangkat Android ter-root, aplikasi masih dapat berkomunikasi dengan server backend. Apa akar masalah utama dan solusi pengamanannya?
    - *A.* Dio client menggunakan adapter web alih-alih adapter IO.
    - *B.* Sistem mempercayai User CA di OS; solusi: konfigurasikan `SecurityContext(withTrustedRoots: false)` dan validasi fingerprint sertifikat secara manual di callback SSL.
    - *C.* Header `Authorization` tidak dienkripsi dengan base64.
    - *D.* URL backend menggunakan port selain 443.

---

### Kunci Jawaban & Evaluasi

#### Kunci Jawaban Bagian 1 & 2
1. **B** - Microtask queue memiliki absolute priority; diselesaikan terlebih dahulu sebelum Event queue berikutnya.
2. **B** - `jsonDecode` bersifat synchronous dan blocking; isolasi background mencegah pemblokiran rendering frame pada main isolate.
3. **C** - Standar HTTP RFC menyatakan `401 Unauthorized` menandakan kredensial autentikasi hilang atau kedaluwarsa.
4. **B** - Isolate Groups (Dart 2.15+) mengizinkan isolasi berbagi garbage collector heap dan program structure tanpa overhead cloning memori awal yang besar.
5. **B** - Method hook native untuk memvalidasi byte sertifikat dan hash SPKI secara eksplisit.
6. **B** - Siklus rekursif pada microtask menahan event loop untuk berpindah ke event antrean rendering UI atau IO (Starvation).
7. **B** - `QueuedInterceptor` menyediakan synchronous lock mechanism pada pipeline network Dio.
8. **B** - SPKI memvalidasi Public Key pair. Sertifikat bisa diperpanjang masa berlakunya tanpa mengganti keypair, mencegah client brick.
9. **C** - Jitter mendistribusikan waktu percobaan retry secara acak untuk mencegah pembebanan server secara terkoordinasi (Thundering Herd).
10. **B** - Native binding pointers, database connections, dan context closures dengan outside references tidak bisa dilewatkan antar isolate boundary.

#### Kunci Jawaban Bagian 3 (Skenario)
11. **B** - Exponential Backoff dengan Full Jitter mengurai thundering herd secara matematis dan melindungi upstream cluster dari DDoS tidak sengaja oleh client.
12. **B** - Memindahkan seluruh parsing loop dan alokasi instansiasi memori model ke background isolate memory heap membebaskan main isolate GC.
13. **B** - Mematikan root CA OS default dan memverifikasi byte DER/SHA-256 fingerprint secara eksplisit mengeliminasi MITM via local trust store injection.

---

## 16. Summary

* **Event Loop Mastery**: Menghindari *Microtask Starvation* dan memisahkan komputasi berat dari main UI Isolate adalah fondasi utama dalam menciptakan aplikasi Flutter yang bebas frame-jank (konsisten 60/120 FPS).
* **Enterprise Concurrency**: Implementasi *QueuedInterceptor* pada Dio mencegah kegagalan beruntun (*cascading 401 failures*) dan menjamin kelancaran auth lifecycle pada aplikasi dengan volume request paralel yang padat.
* **Zero-Trust Networking**: Keamanan layer transport tidak boleh hanya mengandalkan CA bawaan platform. Penggunaan *SPKI SHA-256 Pinning* memberikan perlindungan MITM maksimal sekaligus mempertahankan fleksibilitas rotasi sertifikat berkala.
* **Resilience Patterns**: Penggunaan algoritma *Full Jitter Retry* dan *Circuit Breaker* mentransformasi arsitektur mobile network dari sekadar pasif menjadi sistem yang tangguh (*resilient*) terhadap fluktuasi jaringan skala enterprise.