# SEKSI 01 — IDENTITAS MODUL

*   **Jalur Kurikulum:** 03-Frontend-and-Mobile
*   **Topik Utama:** Flutter Core Architecture & Production Engineering
*   **Bab:** 05 — Advanced State, Network, & Concurrency
*   **Modul:** 01
*   **Judul Modul:** Asynchronous Concurrency, Network & API Layer
*   **Tingkat Kesulitan:** Advanced / Staff-Engineer Track
*   **Prasyarat:** Dart Type System, Flutter Lifecycle, Basic Asynchronous Programming (`Future`/`Stream`), Object-Oriented Design Patterns.

---

# SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, engineer diharapkan mampu:

1.  **Mendekomposisi Execution Model Dart:** Menjelaskan secara presisi siklus hidup Event Loop, interaksi Microtask Queue versus Event Queue, serta eksekusi tugas non-blocking tanpa merusak frame budget (16.6ms / 60fps atau 8.3ms / 120fps).
2.  **Mengimplementasikan Multi-Isolate Concurrency:** Merancang arsitektur paralelisasi menggunakan `Isolate.spawn`, bidirectional `ReceivePort`/`SendPort`, dan `compute()` untuk tugas komputasi intensif (misal: JSON parsing skala besar, dekripsi payload kriptografis).
3.  **Membangun Resilient Networking Pipeline:** Mengembangkan lapisan jaringan enterprise berbasis `Dio` yang mencakup interseptor dinamis untuk silent authentication refresh, distributed exponential backoff retry dengan jitter, dan circuit breaking.
4.  **Menerapkan Strict Type Safety & Parsing Deserialization:** Mengeliminasi runtime type-cast exception (`TypeError`) melalui model serialisasi nir-cacat menggunakan `freezed` dan code generation, serta pengolahan deserialisasi off-main-thread.
5.  **Menerapkan Zero-Trust Security pada Network Layer:** Mengonfigurasi SHA-256 Public Key Pinning (SSL Pinning) native via SecurityContext, payload encryption/integrity validation, dan sanitasi logging data sensitif (PII).

---

# SEKSI 03 — MINDSET & MENTAL MODEL

Dart adalah bahasa *single-threaded by default*. Di platform mobile, main-thread berbagi tanggung jawab langsung dengan proses perenderan UI Flutter Engine (Pipeline: Animate $\rightarrow$ Build $\rightarrow$ Layout $\rightarrow$ Paint $\rightarrow$ Composite).

```
   +-------------------------------------------------------------------+
   |                       FRAME BUDGET (16.6ms)                       |
   |  [UI Build & Layout] -> [Paint] -> [Rasterizer] -> [Frame Rendered]
   +-------------------------------------------------------------------+
       ^
       |-- JIKA ADA CPU BOUND (Parsing JSON 5MB memakan 45ms)
       v
   [!!! JANK DETECTED: DROPPED 3 FRAMES (UI FREEZE TERLIHAT USER) !!!]
```

Mental model yang salah mengasumsikan bahwa kata kunci `async`/`await` memindahkan eksekusi kode ke thread terpisah (background thread). Kenyataan teknisnya:

*   **`async`/`await` BUKAN paralelisasi multi-threading.** `async`/`await` hanyalah *syntactic sugar* di atas `Future` API yang memecah fungsi menjadi callback-callback terjadwal di Event Loop pada thread yang sama.
*   **I/O Bound vs CPU Bound:** Operasi jaringan (I/O) didelegasikan oleh Dart VM ke kernel sistem operasi (epoll/kqueue/IOCP). Saat kernel menunggu data paket TCP/IP, thread Dart menganggur atau mengeksekusi UI frame lain. Sebaliknya, decoding payload JSON sebesar 10MB setelah paket sampai adalah operasi CPU-bound. Jika CPU-bound dijalankan di main isolate, layar aplikasi **pasti mengalami jank (drop frame)**.
*   **Isolate Memory Boundary:** Dart tidak mengadopsi model *shared memory multi-threading* seperti Java atau C++. Setiap Isolate memiliki isolated heap memory sendiri. Tidak ada lock contention, mutex, atau race condition pada memori mentah, namun terdapat overhead komputasi saat melakukan deep-copy data antar-isolate (kecuali menggunakan buffer transfer langsung).

---

# SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

### 1. Dart Event Loop & Task Scheduling Lifecycle

```
[ Inisialisasi Isolate ]
        |
        v
+------------------+
| Eksekusi main()  | <--- Fase Sinkronus (Run to Completion)
+------------------+
        |
        +-----------------------+
        |                       |
        v                       v
+------------------+    +------------------+
| Microtask Queue  |    |   Event Queue    |
| (Prioritas #1)   |    | (Prioritas #2)   |
+------------------+    +------------------+
        |                       |
        |   +---------------+   |
        +-> | Ada Task di   | <-+
            |  Microtask?   |
            +---------------+
                 |       |
            YES  |       | NO
                 v       v
      [Eksekusi Task]  [Ambil 1 Task dari Event Queue]
                 ^       |
                 |       v
                 +-- [Eksekusi Task Event]
                         |
                         v
             [Periksa Microtask Queue Lagi]
```

### 2. Enterprise Network Engine Architecture

```
[UI Layer / State Management (Bloc/Riverpod)]
        |
        | Request Token/Query
        v
[Repository Layer] <--- Konversi DTO ke Domain Entity
        |
        v
[Network API Client (Dio Engine)]
   +---------------------------------------------------------------------+
   |                      Interceptors Pipeline                          |
   |                                                                     |
   | [Auth Interceptor] ---> Tambah Bearer Token                         |
   |          |                                                          |
   |          v                                                          |
   | [Security Interceptor] -> SSL Pinning Validation                    |
   |          |                                                          |
   |          v                                                          |
   | [Logging/Telemetry] --> Metrik Latensi (Sanitasi PII)               |
   +---------------------------------------------------------------------+
        |
        | Kirim HTTP Raw Call
        v
[Remote API Gateway / REST Endpoint]
        |
        | Raw Streamed Bytes / String Response
        v
[Response Pipeline]
        |
        | [401 Unauthorized?] ---> [Token Lock Mutex] -> [Refresh Call]
        |                                                    |
        |                                              Token Diperbarui
        |                                                    |
        +--- Ulangi Request Asli <---------------------------+
        |
        v
[Off-Main-Thread Deserialization Worker]
   +---------------------------------------------------------------------+
   | Isolate Boundary (Compute / Worker Pool)                            |
   |                                                                     |
   |  Raw JSON String                                                    |
   |        |                                                            |
   |        v                                                            |
   |  jsonDecode() -> Map<String, dynamic>                               |
   |        |                                                            |
   |        v                                                            |
   |  DTO.fromJson() -> Strongly Typed Immutable Immutable Model        |
   +---------------------------------------------------------------------+
        |
        | Transfer Ownership / Cloned Instance
        v
[Domain Logic / State Update] -> Render Frame Tanpa Frame-Drop
```

---

# SEKSI 05 — ANATOMI & MEKANISME INTERNAL

### Dart VM Isolate Internals
Setiap Isolate di Dart VM terdiri dari:
1.  **A Single Execution Thread:** Menjalankan instruksi bytecode Dart secara sekuensial.
2.  **Dedicated Heap Memory:** Alokasi memori yang terisolasi sepenuhnya. GC (Garbage Collector) beroperasi secara independen per-isolate tanpa perlu global stop-the-world lock across CPU cores.
3.  **Microtask Queue:** Menampung callback internal yang sangat krusial, dijadwalkan via `scheduleMicrotask()`. Microtask queue selalu dikosongkan hingga nol sebelum Event Loop mengambil antrean berikutnya dari Event Queue.
4.  **Event Queue:** Menampung event eksternal: I/O completion callbacks (jaringan, file sistem), gesture pointer event dari layar, timer events, dan pesan antar-isolate.

### Mekanisme Komunikasi Antar-Isolate
Ketika Isolate A mengirim objek Dart ke Isolate B melalui `SendPort.send(message)`:
*   **Legacy/Deep Copy Model:** Runtime melakukan transitif traversal grafik objek, mengalokasikan memori baru di heap Isolate B, dan menyalin data secara rekursif (copying cost $O(N)$ di mana $N$ adalah ukuran memory footprint grafik objek).
*   **TransferableTypedData Model:** Untuk struktur data bertipe biner (`Uint8List`), memori native C-heap yang mendasari byte buffer dapat "dipindahkan kepemilikannya" (transfer ownership) tanpa penyalinan byte ($O(1)$ transfer time). Isolate A kehilangan akses ke buffer tersebut setelah transfer.

---

# SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### Microtask Starvation
Karena Microtask Queue memiliki prioritas absolut dibandingkan Event Queue, loop mikro yang tidak terkendali akan mengakibatkan *Microtask Starvation*.

```dart
// CONTOH CODE RUNAWAY MICROTASK: ANTI-PATTERN
void induceStarvation() {
  scheduleMicrotask(() => induceStarvation());
}
```
Jika cuplikan di atas dieksekusi, Event Queue tidak akan pernah disentuh. Konsekuensinya: rendering UI terhenti total, input sentuhan diabaikan, dan HTTP I/O callback tidak pernah dipanggil. Penggunaan `scheduleMicrotask` harus dibatasi hanya untuk operasi clean-up internal yang esensial.

### Exponential Backoff dengan Decorrelated Full Jitter
Percobaan rekoneksi naive dengan interval linear (misal: retry tiap 2 detik) saat backend mengalami degradasi kapasitas akan menimbulkan fenomena *Thundering Herd Problem*. Sistem client membanjiri server secara serentak pada interval yang teratur.

Formula standar industri AWS untuk mitigasi thundering herd adalah **Full Jitter**:

$$T_{\text{sleep}} = \text{random}(0, \min(M, B \times 2^{\text{attempt}}))$$

Di mana:
*   $B$ = Base interval (misal: 1 detik).
*   $M$ = Maximum interval (misal: 30 detik).
*   $\text{attempt}$ = Nomor percobaan kegagalan saat ini ($0, 1, 2, \dots$).
*   $\text{random}(0, X)$ = Menghasilkan float acak seragam antara $0$ dan $X$.

Dengan Full Jitter, distribusi lonjakan request disebar secara acak di seluruh skala waktu, meredam beban puncak (spike load) pada API Gateway.

---

# SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah demonstrasi fundamental tentang perbandingan deterministik eksekusi antara operasi synchronous, microtask, event loop, dan paralelisasi via `Isolate.run`.

```dart
import 'dart:async';
import 'dart:isolate';

void main() async {
  print('[1] Main Execution Started - Synchronous');

  // Menjadwalkan tugas pada Event Queue (Prioritas Rendah)
  Future(() {
    print('[5] Event Queue: Normal Future executed');
  });

  // Menjadwalkan delayed task pada Event Queue
  Future.delayed(Duration(milliseconds: 10), () {
    print('[7] Event Queue: Delayed Future executed');
  });

  // Menjadwalkan tugas pada Microtask Queue (Prioritas Tinggi)
  scheduleMicrotask(() {
    print('[3] Microtask Queue: Task 1 executed');
  });

  scheduleMicrotask(() {
    print('[4] Microtask Queue: Task 2 executed');
  });

  // Komputasi CPU-bound dieksekusi di background isolate terpisah
  final isolateResult = await Isolate.run<int>(() {
    // Berjalan di heap independen
    int accumulator = 0;
    for (int i = 0; i < 10000000; i++) {
      accumulator += (i % 2);
    }
    return accumulator;
  });

  print('[6] Isolate Run Finished with result: $isolateResult');

  print('[2] Main Execution Completed - Exiting Main Frame Block');
}
```

---

# SEKSI 08 — ANALISIS BARIS DEMI BARIS

| Baris / Blok | Target Konseptual | Penjelasan Teknis Mendalam |
| :--- | :--- | :--- |
| `print('[1]...')` | Synchronous Frame | Dieksekusi seketika pada call-stack main isolate saat thread diinisiasi. |
| `Future(...)` | Event Queue Insertion | Membungkus fungsi ke dalam blok callback dan meletakkannya di ekor (tail) Event Queue. Tidak akan dieksekusi sampai eksekusi main synchronous dan microtask selesai. |
| `Future.delayed(...)` | Timer Registration | Dart mendaftarkan timer ke internal event-handler VM. Setelah durasi minimal 10ms berlalu, callback dipindahkan ke Event Queue. |
| `scheduleMicrotask(...)` | Microtask Queue | Memasukkan callback ke Microtask Queue. Dieksekusi segera setelah instruksi synchronous `main()` selesai, sebelum event biasa diproses. |
| `Isolate.run(...)` | Thread Spawning | Membuat (spawn) Isolate baru secara temporer, mengeksekusi lambda closure di thread sistem operasi yang terpisah, mengembalikan nilai hasil via port internal, dan langsung menghentikan (kill) isolate secara efisien. |
| `await` pada `Isolate.run` | Non-blocking Suspension | Menangguhkan kelanjutan sisa fungsi `main()` tanpa memblokir thread. Event loop tetap dapat memproses event microtask sementara worker thread Isolate sedang menghitung. |
| `print('[2]...')` | Call-Stack Depletion | Menandakan akhir eksekusi blok sinkronus pertama `main()`, memicu Event Loop untuk mulai menguras Microtask Queue. |

---

# SEKSI 09 — STUDI KASUS NYATA

### Skenario: Production-Grade Fintech Trading Platform Gateway
Sebuah aplikasi sistem enterprise FinTech multinasional memproses feed data portofolio dengan payload JSON berskala 5MB hingga 15MB yang dipancarkan secara terus-menerus melalui endpoint REST. 

**Tantangan Arsitektur:**
1.  **UI Hang / Frame Drop:** Parsing JSON skala besar langsung di main-thread menyebabkan UI terhenti selama 150ms–300ms, mengakibatkan gesture freezing dan animasi stuttering.
2.  **Authentication Race Condition:** Ratusan widget secara reaktif memanggil API bersamaan. Saat access token (JWT) kedaluwarsa (401 Unauthorized), terjadi banjir request token refresh ke authentication server. Jika tidak ada mekanisme antrean terkunci, server me-revoke session karena duplikasi rotasi refresh token.
3.  **Man-in-the-Middle (MitM) Risk:** Risiko penyadapan data finansial pada jaringan Wi-Fi publik tanpa validasi kriptografis sertifikat SSL/TLS.
4.  **Network Instability:** Request kerap terputus saat beralih antara jaringan 4G/5G dan Wi-Fi.

---

# SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Berikut adalah implementasi sistem jaringan enterprise modular yang mencakup: Custom Dio Client, Queued Mutex Lock Refresh Token, SHA-256 SSL Pinning Native, Exponential Backoff Jitter Retry, dan Off-Thread Isolate JSON Deserialization.

### 1. Model & Parsing Architecture

```dart
// portfolio_payload.dart
import 'package:flutter/foundation.dart';

@immutable
class AssetPosition {
  final String symbol;
  final double quantity;
  final double marketPrice;

  const AssetPosition({
    required this.symbol,
    required this.quantity,
    required this.marketPrice,
  });

  factory AssetPosition.fromJson(Map<String, dynamic> json) {
    return AssetPosition(
      symbol: json['symbol'] as String,
      quantity: (json['quantity'] as num).toDouble(),
      marketPrice: (json['market_price'] as num).toDouble(),
    );
  }
}

@immutable
class PortfolioResponse {
  final String accountId;
  final List<AssetPosition> positions;

  const PortfolioResponse({
    required this.accountId,
    required this.positions,
  });

  factory PortfolioResponse.fromJson(Map<String, dynamic> json) {
    return PortfolioResponse(
      accountId: json['account_id'] as String,
      positions: (json['positions'] as List<dynamic>)
          .map((e) => AssetPosition.fromJson(e as Map<String, dynamic>))
          .toList(growable: false),
    );
  }
}
```

### 2. Network Client Engine Enterprise

```dart
// secure_network_client.dart
import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'package:dio/dio.dart';
import 'package:dio/io.dart';
import 'package:flutter/foundation.dart';
import 'portfolio_payload.dart';

/// Secure Token Provider Contract
abstract class ITokenRepository {
  Future<String?> getAccessToken();
  Future<String?> getRefreshToken();
  Future<String> refreshAccessToken(String refreshToken);
  Future<void> clearSession();
}

/// Dynamic SSL Pinning & Enterprise Configured Dio Client
class EnterpriseApiClient {
  late final Dio _dio;
  final ITokenRepository _tokenRepository;
  final Completer<void>? _refreshCompleter = null;

  EnterpriseApiClient({
    required String baseUrl,
    required ITokenRepository tokenRepository,
    required List<String> allowedSha256Fingerprints,
  }) : _tokenRepository = tokenRepository {
    final BaseOptions options = BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 15),
      sendTimeout: const Duration(seconds: 10),
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
      responseType: ResponseType.json,
    );

    _dio = Dio(options);

    _configureSslPinning(allowedSha256Fingerprints);
    _configureInterceptors();
  }

  void _configureSslPinning(List<String> allowedFingerprints) {
    if (kIsWeb) return; // Web mengandalkan native browser certificate validation

    _dio.httpClientAdapter = IOHttpClientAdapter(
      createHttpClient: () {
        final SecurityContext securityContext = SecurityContext(withTrustedRoots: true);
        final HttpClient client = HttpClient(context: securityContext);

        client.badCertificateCallback = (X509Certificate cert, String host, int port) {
          // Konversi SHA-256 DER bytes ke format hex string standar
          final certSha256 = cert.sha256.map((b) => b.toRadixString(16).padLeft(2, '0')).join(':').toUpperCase();
          
          final isMatched = allowedFingerprints.any(
            (fingerprint) => fingerprint.toUpperCase() == certSha256,
          );

          if (!isMatched) {
            // Drop koneksi secara langsung jika certificate fingerprint tidak cocok
            return false;
          }
          return true;
        };
        return client;
      },
    );
  }

  void _configureInterceptors() {
    _dio.interceptors.addAll([
      // 1. Auth & Queue Token Interceptor
      QueuedInterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await _tokenRepository.getAccessToken();
          if (token != null && token.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          return handler.next(options);
        },
        onError: (DioException err, handler) async {
          if (err.response?.statusCode == 401) {
            final RequestOptions requestOptions = err.requestOptions;
            
            try {
              final refreshToken = await _tokenRepository.getRefreshToken();
              if (refreshToken == null) {
                await _tokenRepository.clearSession();
                return handler.next(err);
              }

              // QueuedInterceptorsWrapper mengunci semua request lain saat pemanggilan di bawah berlangsung
              final newAccessToken = await _tokenRepository.refreshAccessToken(refreshToken);

              // Update header authorization dengan token baru
              requestOptions.headers['Authorization'] = 'Bearer $newAccessToken';

              // Eksekusi ulang request yang gagal
              final response = await _dio.fetch(requestOptions);
              return handler.resolve(response);
            } catch (refreshErr) {
              await _tokenRepository.clearSession();
              return handler.next(err);
            }
          }
          return handler.next(err);
        },
      ),

      // 2. Exponential Backoff with Jitter Retry Interceptor
      InterceptorsWrapper(
        onError: (DioException err, handler) async {
          if (_shouldRetry(err)) {
            final requestOptions = err.requestOptions;
            final currentAttempt = (requestOptions.extra['retry_attempt'] as int? ?? 0);
            const maxRetries = 3;

            if (currentAttempt < maxRetries) {
              requestOptions.extra['retry_attempt'] = currentAttempt + 1;
              
              final delay = _calculateJitterDelay(currentAttempt);
              await Future.delayed(delay);

              try {
                final response = await _dio.fetch(requestOptions);
                return handler.resolve(response);
              } catch (retryErr) {
                if (retryErr is DioException) {
                  return handler.next(retryErr);
                }
              }
            }
          }
          return handler.next(err);
        },
      ),
    ]);
  }

  bool _shouldRetry(DioException err) {
    return err.type == DioExceptionType.connectionTimeout ||
        err.type == DioExceptionType.sendTimeout ||
        err.type == DioExceptionType.receiveTimeout ||
        err.type == DioExceptionType.connectionError ||
        (err.response != null && err.response!.statusCode! >= 500);
  }

  Duration _calculateJitterDelay(int attempt) {
    const int baseDelayMs = 1000;
    const int maxDelayMs = 10000;
    final int exponentialBackoff = baseDelayMs * pow(2, attempt).toInt();
    final int ceiling = min(exponentialBackoff, maxDelayMs);
    final int jittered = Random().nextInt(ceiling + 1);
    return Duration(milliseconds: jittered);
  }

  /// Request Method dengan Isolasi Parsing CPU-Bound
  Future<PortfolioResponse> getPortfolio(String portfolioId) async {
    final response = await _dio.get<dynamic>('/v1/portfolios/$portfolioId');

    // Mencegah Jank: Eksekusi mapping data mentah ke DTO di dalam Background Isolate
    final parsedData = await compute(_parsePortfolioBackground, response.data);
    return parsedData;
  }
}

/// Fungsi Parsing Top-Level/Static untuk compute()
PortfolioResponse _parsePortfolioBackground(dynamic rawData) {
  Map<String, dynamic> jsonMap;
  if (rawData is String) {
    jsonMap = jsonDecode(rawData) as Map<String, dynamic>;
  } else if (rawData is Map<String, dynamic>) {
    jsonMap = rawData;
  } else {
    throw const FormatException('Payload format is invalid');
  }
  return PortfolioResponse.fromJson(jsonMap);
}
```

---

# SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Aspek / Karakteristik | `compute()` / `Isolate.run()` | Dedicated Long-Living Isolate | Worker Pool (Multiple Isolates) |
| :--- | :--- | :--- | :--- |
| **Startup Cost** | Relatif tinggi (Spawn & teardown per invocation). | Sekali di awal (Spawn saat startup). | Terjadwal, dialokasikan di awal (Thread-pooling overhead). |
| **Memory Footprint** | Bersifat sementara (GC membersihkan heap segera). | Statis, terus memakan alokasi heap RAM. | Statis tinggi, dikalikan jumlah worker aktif. |
| **Kompleksitas Kode** | Sangat rendah (Mendukung closure/top-level function). | Tinggi (Membutuhkan State Machine & Port Loop). | Sangat tinggi (Membutuhkan Task Queue & Load Balancer). |
| **Use-Case Ideal** | I/O CPU parsing berkala (< 10 kali per menit). | Streaming data WebSocket 100Hz tanpa henti. | Rendering image processing / batch audio filtering lokal. |

| Karakteristik | Raw Dart `HttpClient` | Library `http` | Library `Dio` |
| :--- | :--- | :--- | :--- |
| **Footprint Dependency**| Zero external dependency. | Sangat ringan (Package resmi Dart). | Mengengah (Fitur sangat kaya). |
| **Interceptors Chain** | Tidak ada secara native (Perlu wrapper manual). | Minimalis via class wrapper extension. | Native out-of-the-box (Mendukung Queued mode). |
| **Cancellation Token** | Berbasis raw Socket/HttpClient cancel. | Sulit, tidak didukung secara elegan. | Native via `CancelToken`. |
| **File I/O Stream** | Kompleksitas tinggi. | Standar. | Teroptimasi via Transformer stream interface. |

---

# SEKSI 12 — EDGE CASES & PITFALLS

### 1. The Token Refresh Infinite Loop
Jika endpoint auth refresh (`/auth/refresh`) merespons dengan kode error `401 Unauthorized` (misalnya karena refresh token juga telah usang di backend), interceptor tanpa kondisi pemutus rekursif akan mencoba me-refresh dirinya sendiri terus menerus.
*Mitigasi:* Request options internal wajib memiliki penanda (misalnya: `extra['isRetry'] = true`) dan bypass blok interceptor ketika endpoint yang gagal adalah endpoint token refresh itu sendiri.

### 2. OOM (Out Of Memory) Akibat Transfer Salinan Objek Antar-Isolate
Mentransfer struktur data dynamic JSON yang memuat 100.000 records dari worker isolate ke main isolate via Port dapat melipatgandakan alokasi memori heap (Main isolate memegang salinan + Worker isolate memegang data asal sebelum di-GC).
*Mitigasi:* Lakukan pemfilteran, paginasi, dan perampingan data model di dalam worker isolate. Kirimkan entitas yang hanya dibutuhkan oleh UI layer, bukan raw tree collection yang masif.

### 3. Context Unmounted Memory Leak pada Asynchronous Gap
Memperbarui state UI menggunakan `BuildContext` setelah proses network `await` yang panjang saat pengguna telah menekan tombol "Back" (widget telah di-unmount dari element tree).
*Mitigasi:* Wajib lakukan validasi `if (!context.mounted) return;` segera setelah instruksi `await` selesai sebelum berinteraksi dengan State atau InheritedWidget.

---

# SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### Kesalahan Fatal 1: Salah Mengasumsikan `Future.wait` Berjalan Paralel Secara Multithread
```dart
// KESALAHAN: Mengira parsing dua JSON besar berjalan pada dua thread berbeda
await Future.wait([
  Future(() => parseBigJson(jsonA)), // Tetap berjalan di Event Loop Main Isolate!
  Future(() => parseBigJson(jsonB)), // Tetap berjalan di Event Loop Main Isolate!
]);
```
**Perbaikan:**
Gunakan `compute()` atau `Isolate.run()` untuk memastikan komputasi terjadi di thread terpisah.
```dart
// BENAR: Menggunakan thread worker independen
await Future.wait([
  compute(parseBigJson, jsonA),
  compute(parseBigJson, jsonB),
]);
```

### Kesalahan Fatal 2: Blocking Main Isolate Melalui Parsing JSON Langsung di Interceptor
Mendekode JSON besar di dalam body `onResponse` Interceptor Dio secara sinkronus. Interceptor berjalan di main isolate. Jika respons string berukuran 8MB di-decode via `jsonDecode()` di interceptor, UI tetap akan drop frame.
**Perbaikan:** Ubah konfigurasi default transformer Dio menggunakan custom `BackgroundTransformer` yang memanfaatkan Isolate untuk proses deserialisasi format JSON.

---

# SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1.  **Immutability Strictness:** Seluruh DTO (Data Transfer Object) wajib bersifat immutable (`@immutable`) dengan tipe data eksplisit (hindari tipe `dynamic`).
2.  **Request Cancellation:** Selalu inject `CancelToken` ke dalam pemanggilan layer Repository yang terikat dengan siklus hidup UI Controller/Bloc. Jika pengguna menutup halaman, batalkan request HTTP untuk menghemat bandwidth transmisi data dan pemrosesan thread.
3.  **Unified Error Hierarchy:** Jangan biarkan `DioException` tembus ke Presentation Layer. Bungkus error ke dalam abstraksi Domain Failure (misal: `NetworkFailure`, `UnauthorizedFailure`, `ServerFailure`).
4.  **Security Sanitization:** Jangan pernah mencetak `Header Authorization`, nomor kartu kredit, atau PII (Personally Identifiable Information) ke terminal menggunakan log mentah `print()`. Gunakan custom logger yang me-redact field-field sensitif.

---

# SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

### Custom Background Transformer untuk Dio
Daripada memanggil `compute()` secara manual di setiap pemanggilan repository, integrasikan Isolate secara terpusat pada pipeline `Sync2BackgroundTransformer`.

```dart
// background_transformer.dart
import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

class IsolateTransformer extends BackgroundTransformer {
  @override
  Future<dynamic> transformResponse(
    RequestOptions options,
    ResponseBody responseBody,
  ) async {
    // Ambil string bytes dari response stream
    final rawString = await super.transformResponse(options, responseBody);
    
    // Jika respons berupa JSON string dan bernilai besar, decode di isolate
    if (rawString is String && rawString.length > 50 * 1024) { // > 50 KB
      return compute(_jsonDecodeWorker, rawString);
    }
    
    return jsonDecode(rawString as String);
  }
}

dynamic _jsonDecodeWorker(String text) => jsonDecode(text);
```
Terapkan ke client: `_dio.transformer = IsolateTransformer();`. Hal ini secara transparan menjamin decoding JSON tidak akan pernah mencuri alokasi frame main-thread.

---

# SEKSI 16 — KEAMANAN & HARDENING

### Implementasi Multi-Fingerprint Public Key Pinning

Untuk mengantisipasi rotasi sertifikat berkala pada load balancer tanpa menghentikan fungsi aplikasi versi lama (brick app), simpan minimal satu pin sertifikat aktif dan satu backup pin sertifikat baru (Hot & Cold Pinning):

```dart
// Pins generated via: openssl x509 -in cert.crt -pubkey -noout | openssl pkey -pubin -outform der | openssl dgst -sha256 -hex
const List<String> kProductionPins = [
  'B8:0C:6D:3E:9A:8C:F2:17:A3:4B:82:11:09:5C:DE:0F:77:8A:23:44:09:88:AA:BC:DE:F1:23:45:67:89:0A:BC', // Current Primary Leaf Certificate
  '4A:12:F3:8B:11:2C:9E:5D:88:7A:BC:32:01:99:AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99:AA:BB', // Backup Rotation CA Key
];
```

Tambahkan pula proteksi tampering dengan mengecek flag `SecurityContext.defaultContext` dan cegah eksekusi network client jika perangkat berjalan di dalam environment proxy tak terpercaya tanpa sertifikat root yang valid.

---

# SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

Lacak metric round-trip network performance menggunakan metrics interceptor terdistribusi:

```dart
// metric_telemetry_interceptor.dart
import 'package:dio/dio.dart';
import 'dart:developer' as developer;

class MetricTelemetryInterceptor extends Interceptor {
  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    options.extra['network_start_epoch'] = DateTime.now().microsecondsSinceEpoch;
    super.onRequest(options, handler);
  }

  @override
  void onResponse(Response response, ResponseInterceptorHandler handler) {
    _logMetrics(response.requestOptions, response.statusCode);
    super.onResponse(response, handler);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    _logMetrics(err.requestOptions, err.response?.statusCode ?? 0, error: err);
    super.onError(err, handler);
  }

  void _logMetrics(RequestOptions options, int? statusCode, {Object? error}) {
    final startTime = options.extra['network_start_epoch'] as int?;
    if (startTime != null) {
      final endTime = DateTime.now().microsecondsSinceEpoch;
      final durationMs = (endTime - startTime) / 1000.0;

      developer.postEvent('enterprise.telemetry.network', {
        'path': options.path,
        'method': options.method,
        'status_code': statusCode,
        'latency_ms': durationMs,
        'payload_size_estimate': options.data?.toString().length ?? 0,
        'has_error': error != null,
      });
    }
  }
}
```
Metrik ini dapat diinspeksi secara real-time via DevTools Timeline Protocol atau dikirim ke backend telemetry monitoring (Datadog/NewRelic).

---

# SEKSI 18 — RINGKASAN & CHEAT SHEET

*   **Dart Concurrency Rule:** Async I/O berjalan di Event Queue Main Isolate. CPU-heavy tasks WAJIB dieksekusi di Isolate terpisah.
*   **Event Scheduling Priority:** Code Block Sinkronus $\rightarrow$ Microtask Queue $\rightarrow$ Event Queue.
*   **Isolate Allocation:** Gunakan `compute()` atau `Isolate.run()` untuk task transient (sekali jalan lalu selesai). Gunakan bidirectional persistent isolate untuk socket/stream berkepanjangan.
*   **QueuedInterceptorsWrapper:** Solusi mutlak untuk race condition refresh token 401; request berikutnya ditahan secara sekuensial hingga token baru di-inject.
*   **SSL Pinning:** Lakukan validasi SHA-256 leaf cert fingerprint di layer socket via `badCertificateCallback` native Dart `HttpClient`.
*   **Retry Pattern:** Wajib gunakan Exponential Backoff dipadukan dengan Full Jitter untuk meredam pembebanan berlebih pada upstream server.

---

# SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal 1
Perhatikan urutan kode berikut:
```dart
void test() {
  print('A');
  Future(() => print('B'));
  scheduleMicrotask(() => print('C'));
  Future