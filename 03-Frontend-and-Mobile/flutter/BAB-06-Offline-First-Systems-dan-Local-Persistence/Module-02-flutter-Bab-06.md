# Modul 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi
**Bab 06: Offline-First Systems dan Local Persistence**
**Kategori: 03-Frontend-and-Mobile (Flutter)**

---

## 1. Learning Objective
Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- Mengonfigurasi dan mengoperasikan mesin basis data relasional lokal performa tinggi menggunakan **Drift** (berbasis SQLite) dengan konfigurasi multithreading via **Dart Isolates** dan mode **Write-Ahead Logging (WAL)**.
- Menerapkan arsitektur **Transactional Outbox Pattern** pada sisi klien untuk menjamin sifat *guaranteed delivery* (at-least-once processing) tanpa kehilangan data mutasi lokal (*zero data loss*).
- Merancang dan mengeksekusi strategi rekonsiliasi data dan resolusi konflik multi-master (*Last-Write-Wins*, *Field-Level Merging*, serta prinsip dasar *Conflict-Free Replicated Data Types/CRDT*).
- Mengintegrasikan enkripsi tingkat basis data (*Database-Level Encryption*) menggunakan **SQLCipher** dan hardware-backed key derivation via Android Keystore dan iOS Keychain.
- Mengimplementasikan pipeline migrasi skema basis data terotomatisasi, *data integrity verification*, dan mekanisme *corruption recovery protocol* di lingkungan produksi.

---

## 2. Prerequisite
Sebelum mendalami modul ini, Anda wajib menguasai:
- **Dart Concurrency:** Primitive asynchronous (`Future`, `Stream`), memory model Dart, serta komunikasi antar-thread melalui `Isolate`, `SendPort`, dan `ReceivePort`.
- **Relational Database Internals:** Konsep ACID (*Atomicity, Consistency, Isolation, Durability*), skema relasional, normalisasi data, *indexing* (B-Tree), dan sintaks SQL DDL/DML.
- **Network Programming:** Protokol HTTP/REST, SSE (*Server-Sent Events*), WebSockets, serta semantik idempotensi (*idempotency keys*).
- **Flutter State Management:** Reactive state pattern menggunakan Riverpod, BLoC, atau Signal untuk mengikat *stream* basis data ke antarmuka pengguna (UI).

---

## 3. Concept & Internal Architecture

Membangun sistem *Offline-First* enterprise bukan sekadar meng-cache respons JSON dari REST API ke dalam `SharedPreferences`. Sistem ini menuntut persistensi lokal berperan sebagai *Single Source of Truth* (SSOT), sementara jaringan eksternal hanyalah media sinkronisasi asinkron.

### A. SQLite Storage Engine Internals & WAL Mode
SQLite secara default menggunakan *rollback journal*. Ketika proses menulis terjadi, SQLite mengunci seluruh basis data (*exclusive lock*), menyalin halaman asli ke file jurnal, memodifikasi halaman di basis data, dan menghapus jurnal setelah *commit*. Hal ini memicu *lock contention* tinggi antara operasi baca UI dan operasi tulis sinkronisasi latar belakang.

```
Rollback Journal Mode:
[Reader] ──(Shared Lock)───► [Database File] ◄───(Exclusive Lock)─── [Writer (Blocks Readers!)]

Write-Ahead Logging (WAL) Mode:
[Reader 1] ────────────────► [Database File] (Snapshot T0)
[Reader 2] ────────────────► [Database File] + [WAL File] (Snapshot T1)
[Writer]   ──(Appends)─────► [WAL File] (Non-blocking towards Readers)
```

Pada **Write-Ahead Logging (WAL)**:
1. Pembacaan dan penulisan dapat berjalan secara konkuren. Penulis tidak memblokir pembaca, dan pembaca tidak memblokir penulis.
2. Perubahan data di-*append* secara sekuensial ke dalam file `.wal`. 
3. Pembaca membaca status basis data dari file utama ditambah indeks pada *shared-memory file* (`.shm`) untuk membaca frame terbaru dari file WAL.
4. Secara berkala, SQLite melakukan operasi **Checkpointing** untuk memindahkan halaman terakumulasi dari file WAL kembali ke file basis data utama.

### B. Drift Architecture & Background Isolate Execution
Drift menyediakan *abstraction layer* bertipe aman (*type-safe*) di atas SQLite. Menjalankan operasi basis data intensif (seperti *bulk insert* 10.000 entitas) langsung di UI Isolate akan memicu *dropped frames* (*jank*). Drift mengatasi masalah ini dengan memindahkan seluruh proses eksekusi SQLite engine ke latar belakang (*Background Isolate*) menggunakan komunikasi *port* berbasis serialisasi RPC asinkron.

```
+-------------------------------------------------------------+
|                         UI Isolate                          |
|  [Repository / BLoC]                                        |
|         │                                                   |
|         ▼ (Drift Generated DAO API)                         |
|  [Drift Client (Query Stream)]                              |
+─────────┼───────────────────────────────────────────────────+
          │ SendPort / ReceivePort (Serialized Stream/Queries)
+─────────┼───────────────────────────────────────────────────+
|         ▼                                                   |
|  [Drift Isolate Server Handler]                             |
|         │                                                   |
|         ▼ (Native C FFI Bindings)                           |
|  [sqlite3 Engine with WAL Mode]                             |
|         │                                                   |
|         ▼ (I/O Operations)                                  |
|  [OS File System / NVMe Storage]                            |
|                  Background Isolate                         |
+-------------------------------------------------------------+
```

### C. State Machine: Transactional Outbox Pattern
Untuk mencegah hilangnya data mutasi lokal saat perangkat *offline* atau aplikasi mendadak terhenti (*crash*), mutasi data aplikasi lokal dan pencatatan event mutasi ke antrean (*Outbox Queue*) wajib dieksekusi dalam **satu transaksi atomik lokal yang sama**.

```
[UI Action: "Create Order"]
         │
         ▼
[Local Atomic Transaction] ──(BEGIN TRANSACTION)
         │
         ├───► 1. INSERT INTO orders (id, payload, sync_state='PENDING')
         │
         ├───► 2. INSERT INTO outbox_mutations (id, aggregate_type, payload, status='QUEUED')
         │
         └───► (COMMIT TRANSACTION)
         │
         ▼
[Outbox Sync Worker] ◄─── Emits event via reactive trigger
         │
         ├───► Reads 'QUEUED' records ordered by created_at ASC
         ├───► Sends to Remote Gateway with Idempotency-Key
         │
         ├───► [Success (200/201)] ──► Update Outbox: 'SENT', orders: 'SYNCED'
         ├───► [Conflict (409)]    ──► Invoke Conflict Resolver Engine
         └───► [Network Down]      ──► Backoff Engine (Exponential Backoff + Jitter)
```

### D. Taksonomi Resolusi Konflik
Terdapat tiga strategi resolusi konflik dominan pada arsitektur offline-first enterprise:

| Strategi | Mekanisme | Trade-off Utama | Skenario Penggunaan |
| :--- | :--- | :--- | :--- |
| **Server-Wins** | Klien selalu menimpa status lokal dengan status respons remote. | Sederhana, aman dari divergensi data, namun menghasilkan kehilangan perubahan lokal (*lost updates*). | Data katalog master, data referensi yang dikontrol terpusat (harga produk, stok global). |
| **Client-Wins / LWW (Last-Write-Wins)** | Pembaruan dengan *timestamp* lokal terbaru memenangkan konflik. Menggunakan resolusi berbasis stempel waktu. | Sangat rentan terhadap *Clock Drift* (ketidaksesuaian jam perangkat klien dengan jam server). | Formulir preferensi pengguna tunggal, draf catatan teks non-kritis. |
| **Field-Level / Semantic Merging** | Server/Klien mengevaluasi mutasi per atribut/kolom, bukan per baris utuh. | Memerlukan pelacakan mutasi granular (*dirty fields delta tracking*), kompleksitas logika rekonsiliasi. | Data kolaboratif, update parsial profil pengguna, mutasi multi-petugas lapangan. |

---

## 4. Why & What

### Mengapa Pendekatan Tradisional Gagal?
Aplikasi *naive-online* berasumsi koneksi jaringan selalu stabil. Pola seperti:
```dart
// Pola Naive: Sangat Rentan Gagal di Lapangan
await httpClient.post('/orders', orderData);
await localDb.saveOrder(orderData);
```
Pola ini memiliki cacat arsitektur fatal:
1. Jika koneksi terputus saat request sedang diproses di server, klien mengira request gagal padahal server berhasil (*false negative*). Klien yang mencoba lagi akan menghasilkan duplikasi data.
2. Jika server berhasil merespons tetapi aplikasi mati (*crash*) sebelum `localDb.saveOrder` selesai dieksekusi, data klien dan server langsung mengalami divergensi (*inconsistency*).

### Solusi Arsitektur
Arsitektur **Offline-First via Transactional Outbox Pattern**:
- **What:** Pendekatan arsitektur di mana mutasi data selalu dituliskan ke basis data lokal terlebih dahulu secara atomik, kemudian disinkronisasi ke server secara asinkron di balik layar.
- **Why:** 
  - **Zero UI Blocking:** Latensi operasi tulis berada pada kisaran mikrodetik (kecepatan disk lokal NVMe), bukan ratusan milidetik (latensi jaringan 4G/5G/Edge).
  - **Deterministic State:** Status sinkronisasi persisten (`PENDING`, `SYNCED`, `FAILED_TERMINAL`) mencerminkan kondisi riil sistem setiap saat.

---

## 5. How (Workflow Detail)

Alur kerja engine sinkronisasi dua arah (*Two-Way Synchronization Engine*):

```
+---------------+        +---------------+        +---------------+        +---------------+
|   UI Layer    |        | Local Storage |        | Outbox Worker |        | Remote Server |
+---------------+        +---------------+        +---------------+        +---------------+
        |                        |                        |                        |
        | 1. Execute Command     |                        |                        |
        |----------------------->|                        |                        |
        |                        | 2. ATOMIC: Insert Data |                        |
        |                        |    + Insert Outbox     |                        |
        |                        |------------------      |                        |
        |                        |                 |      |                        |
        |                        |<-----------------      |                        |
        | 3. Render Optimistic   |                        |                        |
        |<-----------------------|                        |                        |
        |                        | 4. Outbox Stream Event |                        |
        |                        |----------------------->|                        |
        |                        |                        | 5. Process Outbox Task |
        |                        |                        |------------------      |
        |                        |                        |                 |      |
        |                        |                        |<-----------------      |
        |                        |                        | 6. HTTP POST Mutasi    |
        |                        |                        |    (Idempotency Key)   |
        |                        |                        |----------------------->|
        |                        |                        |                        | 7. Commit to DB
        |                        |                        |                        |-----------------
        |                        |                        |                        |                |
        |                        |                        |                        |<----------------
        |                        |                        | 8. 200 OK Response     |
        |                        |                        |    (Server Payload)    |
        |                        |                        |<-----------------------|
        |                        | 9. Mark OUTBOX = SENT  |                        |
        |                        |    Update Local Data   |                        |
        |                        |<-----------------------|                        |
        | 10. Emits DB Change    |                        |                        |
        |<-----------------------|                        |                        |
        |                        |                        |                        |
```

1. **Inisiasi Mutasi:** UI memanggil UseCase/Repository.
2. **Transaksi Atomik Lokal:** Database lokal membuka transaksi. Menulis entitas target sekaligus menyisipkan rekod ke tabel `outbox_mutations`.
3. **Optimistic Rendering:** UI mendengarkan query `Stream` lokal (Drift reactive query) dan langsung memicu *re-render* secara instan.
4. **Outbox Polling/Event Triggers:** Outbox Worker menangkap rekod baru berkondisi `QUEUED`.
5. **Eksekusi Jaringan Idempoten:** Worker mengeksekusi request HTTP dengan header `Idempotency-Key` (UUIDv4 berbasis ID mutasi outbox).
6. **Resolusi Respons:**
   - **Sukses:** Status outbox diubah menjadi `SENT`, status data diubah menjadi `SYNCED`.
   - **Gagal Sementara (503/Timeout):** Di-reschedule menggunakan *exponential backoff* dengan penambahan *jitter*.
   - **Konflik Bisnis (409):** Muatan dikirim ke *Conflict Resolver Pipeline* untuk rekonsiliasi state.

---

## 6. Analogy & Diagram ASCII

### Analogi: Kantor Pos Pedalaman
Bayangkan Anda tinggal di daerah pedalaman tanpa sinyal telepon.
- **Rollback Journal vs WAL:** Rollback Journal seperti kantor pos yang menutup pintu gerbang utama setiap kali ada kurir menyortir paket di dalam; tidak ada warga yang boleh masuk untuk sekadar melihat kotak pos mereka. Sedangkan WAL adalah kantor pos dengan dua loket: loket baca tetap melayani warga yang mengecek surat lama, sementara kurir membubuhkan catatan paket baru di papan pengumuman terpisah di luar secara terus-menerus.
- **Transactional Outbox:** Anda menulis surat pesanan barang dan menyalinnya ke dalam "Buku Ekspedisi" Anda sendiri secara bersamaan. Jika kurir datang seminggu kemudian, kurir tinggal mengambil daftar dari Buku Ekspedisi. Jika kurir terjebak badai di tengah jalan, pesanan Anda tidak lenyap dari catatan Anda. Anda tahu persis statusnya belum terkirim.

### Diagram Arsitektur Komponen

```
+───────────────────────────────────────────────────────────────────────────────+
|                           FLUTTER ENGINE RUNTIME                              |
|                                                                               |
|  +─────────────────────────────────────────────────────────────────────────+  |
|  |                             UI ISOLATE                                  |  |
|  |  +──────────────────────+       +────────────────────────────────────+  |  |
|  |  | Presentation Widgets | <──── | Reactive StateNotifier (Riverpod)  |  |  |
|  |  +──────────────────────+       +────────────────────────────────────+  |  |
|  |                                                   ▲                     |  |
|  |                                                   │ Watch Queries       |  |
|  |                                 +────────────────────────────────────+  |  |
|  |                                 | Sync Repository & Outbox Trigger   |  |  |
|  |                                 +────────────────────────────────────+  |  |
|  +───────────────────────────────────────────────────┼─────────────────────+  |
|                                                      │ RPC via Ports          |
|  +───────────────────────────────────────────────────┼─────────────────────+  |
|  |                       BACKGROUND ISOLATE          ▼                     |  |
|  |  +───────────────────────────────────────────────────────────────────+  |  |
|  |  |                  Drift Database Instance                          |  |  |
|  |  |  +──────────────────────+      +────────────────────────────────+ |  |  |
|  |  |  | Target Entity DAOs   |      | Outbox Table DAO               | |  |  |
|  |  |  +──────────────────────+      +────────────────────────────────+ |  |  |
|  |  +────────────────────────────────────────┬──────────────────────────+  |  |
|  |                                           │ SQLite C FFI Call           |  |
|  |  +────────────────────────────────────────▼──────────────────────────+  |  |
|  |  |                   SQLCipher / SQLite Engine Core                  |  |  |
|  |  |     [PRAGMA journal_mode=WAL]  [PRAGMA synchronous=NORMAL]        |  |  |
|  |  +────────────────────────────────────────┬──────────────────────────+  |  |
|  +───────────────────────────────────────────┼─────────────────────────────+  |
+──────────────────────────────────────────────┼────────────────────────────────+
                                               │ File Descriptor
                                               ▼
                              +─────────────────────────────────+
                              | Local Disk Storage (.db & .wal) |
                              +─────────────────────────────────+
```

---

## 7. Practical Implementation (Standard Enterprise Code)

Berikut adalah implementasi menyeluruh sistem Offline-First berbasis Drift Isolate, Transaksi Atomik Outbox, dan Auto-Retry Synchronization Engine.

### A. Dependensi `pubspec.yaml`
```yaml
dependencies:
  flutter:
    sdk: flutter
  drift: ^2.16.0
  sqlite3_flutter_libs: ^0.5.20
  path_provider: ^2.1.2
  path: ^1.9.0
  uuid: ^4.3.3
  http: ^1.2.0

dev_dependencies:
  drift_dev: ^2.16.0
  build_runner: ^2.4.8
```

### B. Definisi Database Schema & DAO (`database.dart`)
```dart
import 'dart:io';
import 'package:drift/drift.dart';
import 'package:drift/native.dart';
import 'package:drift/isolate.dart';
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' as p;

part 'database.g.dart';

// Enum status transaksi outbox
enum SyncStatus { queued, inFlight, synced, failedTerminal }

// Tabel Mutasi Outbox
class OutboxMutations extends Table {
  TextColumn get id => text()(); // UUIDv4
  TextColumn get aggregateType => text().withLength(min: 1, max: 50)();
  TextColumn get aggregateId => text()();
  TextColumn get mutationType => text()(); // CREATE, UPDATE, DELETE
  TextColumn get payloadJson => text()();
  IntColumn get retryCount => integer().withDefault(const Constant(0))();
  IntColumn get status => intEnum<SyncStatus>()();
  TextColumn get lastError => text().nullable()();
  DateTime get createdAt => dateTime().withDefault(currentDateAndTime)();
  DateTime get updatedAt => dateTime().withDefault(currentDateAndTime)();

  @override
  Set<Column> get primaryKey => {id};
}

// Tabel Entitas Bisnis: Orders
class Orders extends Table {
  TextColumn get id => text()();
  TextColumn get customerName => text().withLength(min: 1, max: 100)();
  RealColumn get totalAmount => real()();
  TextColumn get syncStatus => text().withDefault(const Constant('PENDING'))();
  DateTime get updatedAt => dateTime().withDefault(currentDateAndTime)();

  @override
  Set<Column> get primaryKey => {id};
}

@DriftDatabase(tables: [OutboxMutations, Orders])
class AppDatabase extends _$AppDatabase {
  AppDatabase(QueryExecutor e) : super(e);

  @override
  int get schemaVersion => 1;

  @override
  MigrationStrategy get migration => MigrationStrategy(
    onCreate: (Migrator m) async {
      await m.createAll();
    },
    beforeOpen: (details) async {
      // Mengaktifkan WAL mode untuk konkurensi performa tinggi
      await customStatement('PRAGMA journal_mode = WAL;');
      await customStatement('PRAGMA synchronous = NORMAL;');
      await customStatement('PRAGMA foreign_keys = ON;');
    },
  );

  // Transaksi Atomik: Simpan Data + Catat Outbox Mutasi
  Future<void> createOrderAtomically({
    required OrdersCompanion order,
    required String payloadJson,
  }) async {
    return transaction(() async {
      // 1. Insert ke tabel bisnis
      await into(orders).insert(order);

      // 2. Insert ke antrean outbox secara atomik
      await into(outboxMutations).insert(
        OutboxMutationsCompanion.insert(
          id: order.id.value,
          aggregateType: 'ORDER',
          aggregateId: order.id.value,
          mutationType: 'CREATE',
          payloadJson: payloadJson,
          status: SyncStatus.queued,
        ),
      );
    });
  }
}
```

### C. Background Isolate Factory & Connection Manager (`db_connection.dart`)
```dart
import 'dart:io';
import 'package:drift/drift.dart';
import 'package:drift/isolate.dart';
import 'package:drift/native.dart';
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' as p;

class DatabaseConnectionFactory {
  static Future<DriftIsolate> _createDriftIsolate() async {
    final dir = await getApplicationDocumentsDirectory();
    final path = p.join(dir.path, 'enterprise_offline.sqlite');

    return await DriftIsolate.spawn(() {
      return LazyDatabase(() async {
        return NativeDatabase(File(path));
      });
    });
  }

  static Future<AppDatabase> createDatabaseInstance() async {
    final driftIsolate = await _createDriftIsolate();
    final connection = await driftIsolate.connect();
    return AppDatabase(connection);
  }
}
```

### D. Outbox Sync Engine Worker (`outbox_processor.dart`)
```dart
import 'dart:async';
import 'dart:convert';
import 'package:drift/drift.dart';
import 'package:http/http.dart' as http;
import 'database.dart';

class OutboxProcessor {
  final AppDatabase _db;
  final http.Client _httpClient;
  final String _remoteApiEndpoint;
  bool _isProcessing = false;
  Timer? _pollingTimer;

  OutboxProcessor({
    required AppDatabase db,
    required http.Client httpClient,
    required String remoteApiEndpoint,
  })  : _db = db,
        _httpClient = httpClient,
        _remoteApiEndpoint = remoteApiEndpoint;

  void startWorker() {
    // Jalankan siklus outbox setiap 5 detik atau dipicu secara reaktif
    _pollingTimer = Timer.periodic(const Duration(seconds: 5), (_) => triggerSync());
  }

  void stopWorker() {
    _pollingTimer?.cancel();
  }

  Future<void> triggerSync() async {
    if (_isProcessing) return;
    _isProcessing = true;

    try {
      // Ambil transaksi yang belum tersinkronisasi
      final pendingMutations = await (_db.select(_db.outboxMutations)
            ..where((tbl) => tbl.status.equals(SyncStatus.queued.index))
            ..orderBy([(t) => OrderingTerm(expression: t.createdAt, mode: OrderingMode.asc)])
            ..limit(20))
          .get();

      for (final mutation in pendingMutations) {
        await _processSingleMutation(mutation);
      }
    } finally {
      _isProcessing = false;
    }
  }

  Future<void> _processSingleMutation(OutboxMutation mutation) async {
    // Set status menjadi inFlight
    await (_db.update(_db.outboxMutations)..where((t) => t.id.equals(mutation.id))).write(
      OutboxMutationsCompanion(
        status: Value(SyncStatus.inFlight),
        updatedAt: Value(DateTime.now()),
      ),
    );

    try {
      final response = await _httpClient.post(
        Uri.parse('$_remoteApiEndpoint/${mutation.aggregateType.toLowerCase()}s'),
        headers: {
          'Content-Type': 'application/json',
          'X-Idempotency-Key': mutation.id, // Header Idempotensi Mutlak
        },
        body: mutation.payloadJson,
      ).timeout(const Duration(seconds: 15));

      if (response.statusCode >= 200 && response.statusCode < 300) {
        // Berhasil disinkronkan
        await _db.transaction(() async {
          await (_db.update(_db.outboxMutations)..where((t) => t.id.equals(mutation.id))).write(
            OutboxMutationsCompanion(
              status: Value(SyncStatus.synced),
              updatedAt: Value(DateTime.now()),
            ),
          );

          if (mutation.aggregateType == 'ORDER') {
            await (_db.update(_db.orders)..where((t) => t.id.equals(mutation.aggregateId))).write(
              const OrdersCompanion(syncStatus: Value('SYNCED')),
            );
          }
        });
      } else if (response.statusCode == 409) {
        // Penanganan Konflik State: Server Data Divergence
        await _handleConflict(mutation, response.body);
      } else {
        // Server Error (5xx) atau Bad Request (4xx) yang perlu retry
        await _handleFailure(mutation, 'HTTP ${response.statusCode}: ${response.body}');
      }
    } catch (e) {
      // Network Exception / SocketException / Timeout
      await _handleFailure(mutation, e.toString());
    }
  }

  Future<void> _handleFailure(OutboxMutation mutation, String errorMessage) async {
    final nextRetry = mutation.retryCount + 1;
    final isTerminal = nextRetry >= 5;

    await (_db.update(_db.outboxMutations)..where((t) => t.id.equals(mutation.id))).write(
      OutboxMutationsCompanion(
        status: Value(isTerminal ? SyncStatus.failedTerminal : SyncStatus.queued),
        retryCount: Value(nextRetry),
        lastError: Value(errorMessage),
        updatedAt: Value(DateTime.now()),
      ),
    );
  }

  Future<void> _handleConflict(OutboxMutation mutation, String responseBody) async {
    // Resolusi Konflik: Logika Spesifik Bisnis (Server-Wins Baseline Reconciliation)
    final serverJson = jsonDecode(responseBody) as Map<String, dynamic>;
    
    await _db.transaction(() async {
      if (mutation.aggregateType == 'ORDER') {
        await (_db.update(_db.orders)..where((t) => t.id.equals(mutation.aggregateId))).write(
          OrdersCompanion(
            customerName: Value(serverJson['customerName'] as String),
            totalAmount: Value((serverJson['totalAmount'] as num).toDouble()),
            syncStatus: const Value('RESOLVED_SERVER_WINS'),
            updatedAt: Value(DateTime.now()),
          ),
        );
      }

      await (_db.update(_db.outboxMutations)..where((t) => t.id.equals(mutation.id))).write(
        OutboxMutationsCompanion(
          status: Value(SyncStatus.synced),
          lastError: const Value('Resolved via Server-Wins Conflict Resolution'),
          updatedAt: Value(DateTime.now()),
        ),
      );
    });
  }
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Skenario Lapangan: Aplikasi Logistik PT Angkut Global Nusantara
Aplikasi kurir penjemputan barang beroperasi di wilayah geografis pelosok kalimantan tanpa konektivitas seluler kontinu.

- **Karakteristik Skala:** 
  - 15.000 Agen Kurir aktif serentak.
  - Setiap agen memproses rata-rata 300 paket/hari.
  - Total transaksi harian: 4,5 juta pembaruan status pengiriman, mutasi tanda tangan digital, dan data geolokasi presisi.
- **Kondisi Lapangan:** Koneksi internet terputus-putus sepanjang rute delivery; transisi instan dari mode *Offline* ke sinyal EDGE/HSPA secara sporadis.
- **Arsitektur Solusi yang Diimplementasikan:**
  1. **Dual SQLite Engines:** Basis data utama dipartisi antara *Master Data* (hanya-baca, disinkronkan harian via batch compression delta) dan *Transactional Outbox Data* (tulis intensif).
  2. **WAL Churn Optimization:** Membatasi ukuran file WAL maksimum melalui `PRAGMA wal_autocheckpoint = 1000;` untuk mencegah membesarnya file `.wal` melebihi kapasitas memori perangkat *low-end* Android Go Edition.
  3. **Outbox Coalescing (Compaction Algorithm):** Jika kurir memperbarui status paket yang sama 3 kali saat offline (contoh: `DITERIMA` -> `DIKEMAS` -> `DIKIRIM`), mesin lokal melakukan pra-konsolidasi pada antrean outbox lokal sebelum dikirimkan ke cloud. Hanya status mutasi terakhir yang ditransmisikan, menghemat bandwidth seluler hingga 65%.

---

## 9. Trade-offs & Engineering Decisions

```
+─────────────────────────────────────────────────────────────────────────────+
|                         ANALISIS KONSEKUENSI TEKNIS                         |
+─────────────────────────────────────────────────────────────────────────────+
| 1. Drift via Background Isolate                                             |
|    Pros: UI Thread 60-120 FPS konsisten; tidak ada micro-jank akibat disk    |
|          I/O atau JSON deserialization masif.                               |
|    Cons: Serialisasi RPC overhead antar-isolate. Operasi baca/tulis data     |
|          kecil (<2KB) memiliki sedikit latency overhead (~1-3ms) dibanding   |
|          akses langsung di single isolate.                                  |
+-----------------------------------------------------------------------------+
| 2. Mode Konkurensi WAL vs Rollback Journal                                  |
|    Pros: Eliminasi locked database error saat multi-reading dan sync         |
|          menulis bersamaan.                                                 |
|    Cons: Menghasilkan 3 berkas disk (.db, .wal, .shm). Memerlukan penanganan|
|          eksplisit saat proses backup database (harus checkpointing dulu).  |
+-----------------------------------------------------------------------------+
| 3. Resolusi Konflik: LWW (Last-Write-Wins) vs Field-Level Merging           |
|    Pros (LWW): Sangat mudah diimplementasikan, payload jaringan kecil.      |
|    Cons (LWW): Sangat berbahaya di sistem multi-user. Jam perangkat klien    |
|                yang dimanipulasi manual dapat menimpa data server terkini.  |
|    Pros (Field-Level): Kehilangan data sangat minim; field yang tidak       |
|                        berkonflik dapat menyatu secara deterministik.       |
|    Cons (Field-Level): Skema outbox harus melacak field-diff per mutasi;     |
|                        kompleksitas basis data dan engine penggabung tinggi. |
+-----------------------------------------------------------------------------+
```

---

## 10. Common Mistakes & Troubleshooting

### 1. Database Locking Error (`sqlite3.SqliteException: database is locked (code 5)`)
- **Penyebab:** Terjadi ketika koneksi database non-WAL mencoba melakukan transaksi tulis sementara ada transaksi baca/tulis lain yang belum ditutup (*hanging uncommitted transaction*).
- **Troubleshooting & Solusi:**
  - Pastikan `PRAGMA journal_mode = WAL;` aktif di fase `beforeOpen`.
  - Pasang nilai timeout yang masuk akal pada SQLite connection factory:
    ```sql
    PRAGMA busy_timeout = 5000; -- Menunggu hingga 5 detik sebelum melempar exception locked
    ```

### 2. File WAL Membengkak Tanpa Batas (*Unbounded WAL Growth*)
- **Penyebab:** Ada query reactive (`Stream`) yang tetap terbuka dan menahan referensi ke snapshot lama (*long-running read transaction*), mencegah proses *WAL Checkpointing* memindahkan halaman log ke DB utama.
- **Troubleshooting & Solusi:**
  - Hindari operasi query yang membuka cursor tanpa limit atau Stream yang tidak pernah di-*cancel* saat widget di-*dispose*.
  - Eksekusi *passive checkpoint* secara periodik di background worker:
    ```sql
    PRAGMA wal_checkpoint(PASSIVE);
    ```

### 3. Mengabaikan Transaksionalitas Saat Menulis ke Outbox
- **Penyebab:** Memisahkan penyimpanan data entitas dengan pencatatan mutasi outbox dalam blok kode berbeda tanpa *Atomic Database Transaction*.
- **Konsekuensi:** Jika crash terjadi persis di antara kedua operasi, data tersimpan di DB lokal tapi tidak pernah disinkronkan ke cloud seumur hidup (*Phantom Data*).
- **Solusi:** Selalu bungkus dalam method `transaction()` Drift:
  ```dart
  await db.transaction(() async {
    await db.into(db.orders).insert(orderCompanion);
    await db.into(db.outboxMutations).insert(outboxCompanion);
  });
  ```

---

## 11. Best Practices & Production Checklist

- [ ] **WAL Mode Aktif:** Verifikasi via inspect query: `PRAGMA journal_mode;` mengembalikan hasil `wal`.
- [ ] **Busy Timeout Dikonfigurasi:** Nilai `PRAGMA busy_timeout = 5000;` disetel pada setiap koneksi baru.
- [ ] **Atomic Outbox Enforced:** Tidak ada operasi mutasi data di aplikasi yang membypass tabel outbox tanpa transaksi terintegrasi.
- [ ] **Idempotensi Global:** Seluruh request mutasi remote menyematkan HTTP Header `X-Idempotency-Key` bertipe UUIDv4 yang terikat dengan ID outbox.
- [ ] **Isolation Separation:** Operasi database Drift berjalan pada `DriftIsolate` di luar UI Isolate.
- [ ] **Exponential Backoff dengan Full Jitter:** Algoritma pengulangan outbox menerapkan formula:
  $$\text{Sleep} = \text{random}(0, \min(M, T_{\text{base}} \times 2^{\text{retry}}))$$
  Guna mencegah fenomena *Thundering Herd Problem* pada API Gateway ketika server pulih dari insiden *downtime*.
- [ ] **Enkripsi Data At-Rest:** SQLCipher aktif dengan kunci master bersumber dari hardware-backed storage (`flutter_secure_storage` yang mengintegrasikan Android Keystore / iOS Keychain).

---

## 12. Hands-on Practice

Buatlah implementasi lengkap pada direktori proyek: `hands-on/m02/`

### File: `hands-on/m02/test/idempotency_outbox_test.dart`
Uji ketahanan arsitektur Outbox terhadap kegagalan jaringan dan duplikasi data.

```dart
import 'dart:convert';
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

// Import implementasi yang telah dibuat di langkah 7
import 'package:app/database.dart';
import 'package:app/outbox_processor.dart';

void main() {
  late AppDatabase db;

  setUp(() {
    // Jalankan database in-memory untuk pengujian unit
    db = AppDatabase(NativeDatabase.memory());
  });

  tearDown(() async {
    await db.close();
  });

  test('Outbox Processor harus mengeksekusi request idempoten dan mengupdate status menjadi SYNCED', () async {
    final recordedHeaders = <Map<String, String>>[];

    // Mock Client untuk menyimulasikan server remote
    final mockClient = MockClient((request) async {
      recordedHeaders.add(request.headers);
      return http.Response(jsonEncode({'status': 'SUCCESS'}), 201);
    });

    final processor = OutboxProcessor(
      db: db,
      httpClient: mockClient,
      remoteApiEndpoint: 'https://api.mocked.internal',
    );

    // 1. Simpan order transaksi secara lokal
    final orderId = 'ORD-001-TEST';
    await db.createOrderAtomically(
      order: OrdersCompanion.insert(
        id: orderId,
        customerName: 'Budi Santoso',
        totalAmount: 150000.0,
      ),
      payloadJson: jsonEncode({
        'id': orderId,
        'customerName': 'Budi Santoso',
        'totalAmount': 150000.0,
      }),
    );

    // 2. Jalankan sync processor
    await processor.triggerSync();

    // 3. Verifikasi: Status Outbox dan Data Bisnis telah tersinkron
    final outboxEntry = await (db.select(db.outboxMutations)..where((t) => t.id.equals(orderId))).getSingle();
    final orderEntry = await (db.select(db.orders)..where((t) => t.id.equals(orderId))).getSingle();

    expect(outboxEntry.status, SyncStatus.synced);
    expect(orderEntry.syncStatus, 'SYNCED');
    expect(recordedHeaders.first['X-Idempotency-Key'], orderId);
  });
}
```

---

## 13. Exercises

### Level Easy
Modifikasi skema tabel `OutboxMutations` untuk menambahkan kolom `priority` (tipe data integer: `0 = Low`, `1 = Normal`, `2 = Critical`). Ubah query seleksi pada `OutboxProcessor` agar mengeksekusi mutasi dengan prioritas tertinggi (`Critical`) terlebih dahulu sebelum memproses mutasi bertaraf `Normal` atau `Low`.

### Level Medium
Rancang dan implementasikan skema **Data Compression Delta** pada payload Outbox. Jika sebuah entity profil diupdate di mana hanya atribut `phoneNumber` yang berubah dari 20 atribut yang ada, outbox tidak boleh mengirimkan seluruh payload profil, melainkan hanya menyimpan dan mentransmisikan *diff object* (`{"patch": {"phoneNumber": "08123456789"}}`). Buat fungsi perbandingan deep-equality untuk menghasilkan diff tersebut.

### Level Hard
Implementasikan custom SQLite Engine checkpoint coordinator di Flutter Isolate terpisah yang memantau ukuran file basis data lokal `.wal` secara real-time. Jika ukuran file `.wal` melebihi threshold 50MB (indikator penulisan outbox yang sangat masif tanpa kesempatan checkpoint otomatis), paksa eksekusi `PRAGMA wal_checkpoint(TRUNCATE)` tanpa mengganggu Stream Query reaktif yang sedang berjalan di UI Layer. Pastikan jika ada transaksi aktif, thread menunggu dengan non-blocking state machine.

---

## 14. Architecture Challenge (Studi Kasus Ekstrem)

**Skenario:** Anda adalah Principal Mobile Architect sebuah aplikasi *Stock Inventory Opname* di sebuah gudang seluas 100.000 meter persegi. Lima orang petugas menghitung stok varian SKU barang yang sama secara bersamaan di lorong berbeda tanpa koneksi internet sama sekali selama 4 jam berturut-turut.
- Setiap petugas menambah dan mengurangi jumlah stok barang fisik yang ditemukan di rak masing-masing.
- Kondisi awal SKU-A di server saat mereka mulai opname adalah `stok = 100`.
- Petugas 1 menginput: `+10`, lalu `-2` (Total lokal: 108).
- Petugas 2 menginput: `-5`, lalu `+20` (Total lokal: 115).
- Petugas 3 menginput: `+3` (Total lokal: 103).
- Petugas 4 dan 5 tidak menginput mutasi apa pun pada SKU-A.

Saat kelima perangkat mendekat ke pintu gerbang gudang dan tersambung ke Wi-Fi secara serentak:
- **Tantangan:** Rancang sistem offline-first yang menggunakan arsitektur **PN-Counter (Positive-Negative Counter)** berbasis **CRDT (Conflict-Free Replicated Data Types)** yang diimplementasikan di atas SQLite/Drift. Sistem harus mampu menyatukan status inventaris SKU-A secara deterministik tanpa terjadi *race condition* atau hilangnya data mutasi petugas mana pun, **tanpa mengandalkan jam sistem (Wall Clock) dan tanpa bergantung pada penguncian terpusat (Pessimistic Locking) di server**.
- Tuliskan dokumentasi rancangan teknis:
  1. Skema relasional tabel drift untuk melacak state CRDT per node/perangkat.
  2. Fungsi merge logis `merge(State local, State remote) -> State resolved`.
  3. Bukti matematis bahwa fungsi merge tersebut bersifat *Associative*, *Commutative*, dan *Idempotent* ($A \star B = B \star A$; $(A \star B) \star C = A \star (B \star C)$; $A \star A = A$).

---

## 15. Quiz Evaluasi Pemahaman

### Bagian A: Konseptual Fundamental (5 Soal)
1. **Mengapa SQLite dalam mode Rollback Journal standar rentan memicu jank pada UI Flutter saat background sync berlangsung?**
   - *Jawaban:* Karena mode Rollback Journal menggunakan penguncian eksklusif (*Exclusive Lock*) saat operasi tulis berjalan. Ketika background worker melakukan modifikasi data masif, pembacaan query oleh UI thread akan diblokir total hingga transaksi tulis selesai, menyebabkan *frame rate drop*.
2. **Apa fungsi utama dari berkas `.shm` pada SQLite berkonfigurasi WAL?**
   - *Jawaban:* Berkas `.shm` (*shared-memory*) berfungsi sebagai indeks penunjuk (*index map*) frame data yang berada di dalam berkas WAL, memungkinkan pembaca mencari versi snapshot data terbaru tanpa harus memindai seluruh berkas WAL secara sekuensial.
3. **Apa perbedaan mendasar antara implementasi Isolate manual via `Isolate.spawn()` murni dengan `DriftIsolate` pada library Drift?**
   - *Jawaban:* `DriftIsolate` secara otomatis mengorkestrasi multiplexing query, serialisasi DTO query over ports, sinkronisasi notifikasi mutasi ke *reactive stream clients*, dan manajemen lifecycle koneksi C-level pointer secara terpusat tanpa harus membangun RPC protocol custom manual.
4. **Mengapa *timestamp* perangkat lokal (misal: `DateTime.now()`) tidak dapat diandalkan sebagai basis rekonsiliasi data *Last-Write-Wins* di sistem terdistribusi offline-first?**
   - *Jawaban:* Karena adanya fenomena *Clock Drift* dan kemungkinan manipulasi waktu manual oleh pengguna di pengaturan sistem operasi perangkat, yang dapat menyebabkan data usang menimpa data yang lebih baru secara tidak sah.
5. **Jelaskan peran *Idempotency Key* dalam transaksi outbox synchronization!**
   - *Jawaban:* Menjamin bahwa request mutasi yang dikirim berulang kali (misalnya akibat *network timeout* pada layer respons) hanya akan diproses dan dieksekusi tepat satu kali oleh server, mencegah duplikasi mutasi di sisi remote.

### Bagian B: Analisis & Pemecahan Masalah (5 Soal)
6. **Perangkat mengalami crash tepat setelah mutasi data lokal dimasukkan ke tabel bisnis, tetapi sebelum entri outbox tersimpan. Bagaimana arsitektur Transactional Outbox mengatasi masalah ini?**
   - *Jawaban:* Masalah ini dieliminasi dengan mengeksekusi kedua operasi di dalam blok transaksi atomik SQLite tunggal (`db.transaction(...)`). Jika aplikasi crash di tengah proses, SQLite engine secara otomatis me-rollback perubahan entitas bisnis, menjaga konsistensi state lokal.
7. **Jika sebuah request mutasi menghasilkan status HTTP 400 (Bad Request), apakah Outbox Engine harus menjadwalkan *exponential backoff retry*? Mengapa?**
   - *Jawaban:* Tidak. HTTP 400 mengindikasikan *Client Error* deterministik (payload korup/tidak valid). Mengulang pengiriman dengan muatan identik akan terus menghasilkan galat yang sama. Status mutasi harus ditandai sebagai `FAILED_TERMINAL` untuk diinvestigasi via audit log.
8. **Kapan teknik *Field-Level Merging* lebih direkomendasikan daripada *Server-Wins* dalam penanganan respons konflik (HTTP 409)?**
   - *Jawaban:* Saat aplikasi melibatkan formulir masif dengan multi-atribut di mana pengguna lokal dan sistem remote dapat memperbarui bagian atribut yang berbeda secara bersamaan tanpa menimbulkan kontradiksi nilai bisnis.
9. **Mengapa perintah `PRAGMA synchronous = OFF;` sangat berbahaya diterapkan pada basis data lokal di lingkungan produksi mobile?**
   - *Jawaban:* Karena mode ini menginstruksikan SQLite untuk tidak menunggu konfirmasi penulisan disk OS (flush cache to disk). Jika baterai ponsel mendadak habis atau sistem operasi crash, berkas database SQLite memiliki probabilitas tinggi mengalami korupsi data permanen.
10. **Bagaimana Stream Query Drift mengetahui bahwa sebuah data telah berubah di tabel target dan harus memancarkan data baru ke UI?**
    - *Jawaban:* Drift mempertahankan tabel dependensi (*table stream invalidation manager*). Setiap kali operasi mutasi (`insert`, `update`, `delete`) selesai di-commit pada sebuah tabel, Drift Isolate memicu sinyal pembaruan ke seluruh active listeners yang mereferensikan tabel tersebut.

### Bagian C: Skenario Kasus Produksi (3 Soal)

#### Skenario 1: Penanganan Broken Pipes & Memory Exhaustion pada Batch Sync
Sebuah tablet kurir menerima pembaruan masif berisi 80.000 data inventaris paket saat terhubung ke Wi-Fi hub distribusi. Aplikasi mendadak ditutup paksa oleh Android OS (*Out-Of-Memory Killer* / SIGKILL) saat memproses respons JSON payload tersebut.
- **Pertanyaan:** Identifikasi dua titik kelemahan pemrosesan memori tersebut dan rekomendasikan solusinya secara teknis!
- **Solusi Rekayasa:**
  1. *Kelemahan:* Mendekode JSON array masif secara monolitik (`jsonDecode(response.body)`) memuat seluruh pohon objek ke heap memory UI Isolate sekaligus.
     *Solusi:* Terapkan *streaming JSON parsing* menggunakan library seperti `json_stream` atau memproses response chunk-by-chunk via chunked HTTP stream.
  2. *Kelemahan:* Menyisipkan 80.000 row dalam batch raksasa tunggal menembus batas memory binding SQLite variables limit.
     *Solusi:* Pecah proses persistensi menjadi sub-batch (misalnya 500 entri per transaksi) dengan eksekusi di Background Isolate menggunakan Drift `batch((b) => b.insertAll(...))`.

#### Skenario 2: Ghost Mutation Divergence
Seorang teknisi lapangan mengedit data inspeksi turbin (ID: `TRB-88`). Di saat bersamaan, teknisi lain menghapus objek `TRB-88` langsung di server back-office. Ketika teknisi pertama kembali online, outbox worker mengirimkan pembaruan untuk `TRB-88`, tetapi remote server mengembalikan respons `404 Not Found`.
- **Pertanyaan:** Bagaimana seharusnya Outbox Worker menangani status `404 Not Found` pada data lokal yang masih eksis tersebut secara konsisten?
- **Solusi Rekayasa:**
  1. Engine harus menginterpretasikan `404 Not Found` pada operasi UPDATE sebagai kondisi *Tombstoned/Deleted at Remote*.
  2. Outbox Worker menandai rekod outbox sebagai `RESOLVED_ABORTED`.
  3. Menjalankan transaksi lokal untuk menandai entitas lokal `TRB-88` sebagai `is_deleted = true` atau memindahkannya ke tabel arsip konflik (`tombstone_records`), lalu menampilkan notifikasi non-blocking ke teknisi bahwa data telah dihapus di server pusat.

#### Skenario 3: Forensic Database Corruption Protocol
Pengguna kelas enterprise melaporkan bahwa setelah perangkat mereka mengalami *abnormal system shutdown* saat penulisan data berlangsung, aplikasi menampilkan error `SqliteException(11): database disk image is malformed`.
- **Pertanyaan:** Tuliskan prosedur pemulihan bencana (*Disaster Recovery Protocol*) terotomatisasi yang harus dieksekusi oleh aplikasi Flutter saat mendeteksi error code 11 ini saat inisialisasi basis data!
- **Solusi Rekayasa:**
  1. Tangkap `SqliteException` dengan *extended error code 11* pada initialization wrapper database.
  2. Segera putuskan koneksi (`db.close()`).
  3. Lakukan isolasi forensik: Ubah nama file berkas yang korup dari `app.sqlite` menjadi `app_corrupted_[timestamp].sqlite.bak` untuk investigasi crash-dump reporting.
  4. Periksa apakah terdapat snapshot backup lokal terakhir yang valid (misal: berkas backup terenkripsi harian).
  5. Jika tidak ada backup valid: Inisialisasi basis data kosong baru, jalankan migrasi skema normal, dan jadwalkan worker untuk menarik *Initial Full State Snapshot* dari server remote (Server-Recovery Pull).

---

## 16. Summary

1. **Arsitektur Offline-First Sejati** memperlakukan penyimpanan lokal sebagai *Single Source of Truth* mutlak; antarmuka pengguna tidak pernah bergantung secara synchronous pada latensi dan status ketersediaan koneksi internet.
2. **SQLite Write-Ahead Logging (WAL)** memfasilitasi konkurensi tingkat tinggi yang memisahkan operasi pembacaan data oleh UI Thread dari penulisan mutasi oleh sinkronisasi latar belakang, mengeliminasi galat `database is locked`.
3. **Dart/Drift Isolates** memindahkan overhead I/O komputasi dan serialisasi objek basis data ke thread terpisah, menjamin render UI tetap berada pada performa optimal 60/120 FPS tanpa *jank*.
4. **Transactional Outbox Pattern** yang dijalankan secara atomik bersama pembaruan data lokal menjamin sifat keandalan sistem terdistribusi (*Guaranteed Delivery* / At-Least-Once Execution) yang kebal terhadap *abnormal process termination*.
5. Penggunaan **Idempotency Keys** pada level protokol jaringan dan pemilihan strategi rekonsiliasi yang deterministik adalah pondasi utama integritas data pada sistem sinkronisasi terdistribusi skala enterprise.