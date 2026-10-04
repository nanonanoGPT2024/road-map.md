# Bab 06 Module 01: Offline-First Systems & Local Persistence

---

## SEKSI 01 — IDENTITAS MODUL
* **Track:** Frontend & Mobile Engineering
* **Kategori:** 03-Frontend-and-Mobile
* **Topik:** Offline-First Systems & Local Persistence
* **Level:** Advanced (Staff / Principal Mobile Engineer)
* **Prasyarat:** Dart 3.x, Flutter Internals, Asynchronous Programming (Streams/Futures), Clean Architecture, Basic SQL & Key-Value DB knowledge.

---

## SEKSI 02 — LEARNING OBJECTIVES
Pada akhir modul ini, peserta didik mampu:
1. Merancang dan mengimplementasikan arsitektur *Offline-First* berbasis *Single Source of Truth* (SSOT) menggunakan SQLite (`sqflite` / `drift`) dan Key-Value Store yang aman (`flutter_secure_storage`).
2. Mengembangkan engine *two-way synchronization* dengan *Conflict Resolution Strategy* (LWW, Field-Level Merge, CRDT concept).
3. Mengonstruksi sistem *Optimistic UI Update* yang resilien dengan mekanisme rollback transaksi otomatis ketika sinkronisasi gagal.
4. Mendesain sistem antrean mutasi lokal (*Outbox Pattern*) yang persisten terhadap proses pembunuhan aplikasi (*app kill/crash*), dilengkapi algoritma *Exponential Backoff* dan *Jitter*.
5. Menjamin integritas data relasional lokal, mitigasi kebocoran memori pada *Stream-based queries*, dan mengamankan enkripsi data at-rest menggunakan SQLCipher.

---

## SEKSI 03 — MINDSET & MENTAL MODEL
Dalam rekayasa sistem *Offline-First*, jaringan internet tidak boleh diasumsikan sebagai media transmisi yang selalu tersedia (*always-on*), melainkan sebagai **mekanisme background opsional untuk sinkronisasi eventual consistency**.

```
Mental Model Tradisional (Network-First):
[UI] ---> [API Request] ---> [Remote Server] ---> [Simpan ke Local DB] ---> [Update UI]
*Kelemahan: Latensi jaringan memblokir interaksi pengguna; gagal total saat offline.

Mental Model Offline-First (SSOT):
[UI] <===(Stream)=== [Local Database (SSOT)]
  │                          ▲
  │ (User Mutasi)            │ (Write Local & Commit Mutasi)
  ▼                          │
[Outbox/Command Engine] ─────┘
  │
  └───(Background Sync / Dequeue)───> [Remote Gateway / API]
```

Database lokal adalah **satu-satunya kebenaran mutlak** bagi antarmuka pengguna (UI). UI tidak pernah menunggu respon HTTP remote untuk mengubah kondisinya. UI bereaksi terhadap *stream* reaktif dari database lokal. Mutasi yang diinisiasi oleh pengguna ditulis langsung ke database lokal secara transaksional bersamaan dengan pendaftaran mutasi ke dalam tabel *Outbox*. Engine sinkronisasi berjalan secara independen di latar belakang untuk menyelesaikan status data ke server remote.

---

## SEKSI 04 — ARSITEKTUR & DIAGRAM ALUR

Berikut adalah arsitektur terpadu *Outbox Synchronization Pattern* dengan strategi *Conflict Resolution*:

```
+---------------------------------------------------------------------------------------+
|                                      PRESENTATION                                     |
|  [Flutter Widget Tree] <====== (Watch Stream) ====== [StateNotifier / BLoC / Store]   |
+------------------------------------------------------------------+--------------------+
                                                                   | Dispatch Intent
                                                                   v
+------------------------------------------------------------------+--------------------+
|                                    DOMAIN LAYER                                       |
|  [UseCases / Interactors] : Execute Business Logic Validation                         |
+------------------------------------------------------------------+--------------------+
                                                                   |
                                                                   v
+---------------------------------------------------------------------------------------+
|                                     DATA LAYER                                        |
|                                                                                       |
|  +---------------------------------------------------------------------------------+  |
|  | [Repository Layer]                                                              |  |
|  |  - Write Optimistic Entity ke Local DB                                          |  |
|  |  - Enqueue payload mutasi ke Outbox Table (Atomic Transaction)                   |  |
|  +---------------------------------------------------------------------------------+  |
|            |                                                         |                |
|            v (Local SQLite/Drift Engine)                             v (Sync Trigger) |
|  +-------------------------+                     +----------------------------------+ |
|  |   LOCAL PERSISTENCE     |                     |         OUTBOX SYNC ENGINE       | |
|  | +---------------------+ |                     | +------------------------------+ | |
|  | | Domain Entities     | |                     | | Read Pending Outbox Jobs     | | |
|  | | [id, sync_state...] | |                     | +--------------+---------------+ | |
|  | +---------------------+ |                     +----------------|-----------------+ |
|  | | Outbox Table        | |                                      |                   |
|  | | [job_id, payload...] | |                                      v                   |
|  | +---------------------+ |                     +----------------------------------+ |
|  +-------------------------+                     | [Conflict Resolution Strategy]   | |
|            ▲                                     | - Last-Write-Wins (Timestamp)    | |
|            │                                     | - Server-Wins / Vector Clocks    | |
|            │ (Update sync_state / Reconcile)     +----------------+-----------------+ |
|            |                                                      |                   |
|            +------------------------------------------------------+                   |
|                                                                   | Execute HTTP Push |
+-------------------------------------------------------------------|-------------------+
                                                                    v
+---------------------------------------------------------------------------------------+
|                                  REMOTE INFRASTRUCTURE                                |
|  [Edge Gateway / Reverse Proxy] ---> [Backend Distributed Database / Message Broker]  |
+---------------------------------------------------------------------------------------+
```

---

## SEKSI 05 — ANATOMI & MEKANISME INTERNAL

Sistem *Offline-First* enterprise bergantung pada tiga mekanisme fundamental:

### 1. The Reactive Loop (Stream-based Persistence)
Menggunakan SQLite dengan notifikasi reaktif (melalui `Stream` Dart). Ketika ada mutasi pada tabel `orders`, driver database atau lapisan abstraksi (seperti Stream Controller pembungkus SQLite) memicu event perubahan, menginstruksikan layer UI untuk me-*render* ulang data yang telah diubah secara lokal dalam hitungan sub-milidetik.

### 2. Transactional Mutation Outbox
Menyimpan mutasi data dan *job outbox* dalam satu blok transaksi ACID lokal (`BEGIN TRANSACTION` -> `COMMIT`). Hal ini menjamin bahwa jika aplikasi ditutup atau sistem crash tepat saat data ditulis, tidak akan terjadi kondisi inkonsisten di mana data lokal berubah tetapi mutasi jaringan tidak pernah dikirimkan, atau sebaliknya.

### 3. Sync State Engine & Tombstoning
Untuk mendukung penghapusan data secara *offline-first*, sistem tidak boleh langsung mengeksekusi `DELETE FROM table WHERE id = ?`. Melakukan hal ini akan menghilangkan konteks bahwa data tersebut pernah ada saat sinkronisasi ke server. Sebagai gantinya, digunakan teknik **Soft Deletes / Tombstones**:
* Menandai entitas dengan kolom `is_deleted = 1` dan `is_dirty = 1`.
* Saat sinkronisasi berhasil dikonfirmasi oleh remote server, record tersebut dapat dibersihkan secara lokal (*hard delete*) atau dibiarkan dengan tanda `is_dirty = 0`.

---

## SEKSI 06 — DEEP DIVE KONSEP & TEORI TEKNIS

### 1. CAP Theorem & PACELC dalam Arsitektur Mobile
Aplikasi mobile pada dasarnya adalah sistem terdistribusi. Ketika koneksi terputus, sistem mengalami *Network Partition* ($P$). Berdasarkan CAP Theorem, mobile app harus memilih antara *Availability* ($A$) atau *Consistency* ($C$). 
Sistem *Offline-First* secara mutlak memilih **Availability**: aplikasi harus selalu dapat menerima interaksi *Read* dan *Write*. Konsekuensinya, *Consistency* yang dianut adalah **Eventual Consistency**.

### 2. Strategi Resolusi Konflik (Conflict Resolution)
Saat dua node (Client A dan Remote Server) memodifikasi record yang sama dalam jendela waktu sinkronisasi, konflik terjadi. 

* **Last-Write-Wins (LWW):** Bergantung pada *timestamp* mutasi. Node dengan *timestamp* paling akhir menimpa data sebelumnya.
  $$\text{Target} = \max(T_{\text{local}}, T_{\text{remote}})$$
  *Kelemahan:* Sangat rentan terhadap *Clock Skew* (ketidaksesuaian jam sistem hardware lokal).
* **Field-Level Merging:** Server membedah JSON payload dan membandingkan *timestamp* per-field, bukan per-record.
* **Tombstone Lifecycle:**
  Record lokal memiliki status:
  * `DRAFT / DIRTY_CREATE`: Dibuat saat offline, belum memiliki Server ID definitif.
  * `SYNCED`: Konsisten penuh dengan state remote.
  * `DIRTY_UPDATE`: Pernah sinkron, namun ada modifikasi offline lokal.
  * `TOMBSTONE`: Ditandai untuk dihapus di server.

---

## SEKSI 07 — CONTOH KODE FUNDAMENTAL

Berikut adalah implementasi fundamental *Engine Outbox Transactional* menggunakan `sqflite` murni (tanpa ORM) untuk memahami lapisan abstraksi terendah.

```dart
// lib/core/database/sqlite_offline_core.dart
import 'dart:convert';
import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart';

enum SyncStatus { synced, dirty, draft, tombstone }

class CoreDatabaseManager {
  static final CoreDatabaseManager instance = CoreDatabaseManager._internal();
  static Database? _database;

  CoreDatabaseManager._internal();

  Future<Database> get database async {
    if (_database != null) return _database!;
    _database = await _initDatabase();
    return _database!;
  }

  Future<Database> _initDatabase() async {
    final dbPath = await getDatabasesPath();
    final path = join(dbPath, 'offline_first_core.db');

    return await openDatabase(
      path,
      version: 1,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE products (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            sync_status TEXT NOT NULL,
            updated_at INTEGER NOT NULL
          )
        ''');

        await db.execute('''
          CREATE TABLE sync_outbox (
            mutation_id TEXT PRIMARY KEY,
            aggregate_id TEXT NOT NULL,
            action TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            retry_count INTEGER NOT NULL DEFAULT 0
          )
        ''');
      },
    );
  }

  Future<void> saveProductOptimistically({
    required String id,
    required String name,
    required double price,
  }) async {
    final db = await database;
    final now = DateTime.now().millisecondsSinceEpoch;

    // Transaksi ACID: Tulis Data Lokal & Daftarkan ke Outbox secara Atomik
    await db.transaction((txn) async {
      await txn.insert(
        'products',
        {
          'id': id,
          'name': name,
          'price': price,
          'sync_status': SyncStatus.dirty.name,
          'updated_at': now,
        },
        conflictAlgorithm: ConflictAlgorithm.replace,
      );

      final outboxPayload = jsonEncode({
        'id': id,
        'name': name,
        'price': price,
        'updated_at': now,
      });

      await txn.insert(
        'sync_outbox',
        {
          'mutation_id': 'mut_$now\_$id',
          'aggregate_id': id,
          'action': 'UPSERT',
          'payload': outboxPayload,
          'created_at': now,
          'retry_count': 0,
        },
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    });
  }
}
```

---

## SEKSI 08 — ANALISIS BARIS DEMI BARIS

* **Baris 24–47 (`onCreate` schema):** Database diinisialisasi dengan membuat dua tabel terpisah: tabel entitas data (`products`) dan tabel antrean kerja (`sync_outbox`). Skema ini memisahkan representasi data saat ini dari riwayat instruksi sinkronisasi.
* **Baris 30:** `sync_status TEXT NOT NULL` melacak kondisi sinkronisasi tiap baris. Nilai ini menjadi penentu apakah record lokal perlu diperbarui oleh sinkronisasi background atau sedang menunggu antrean upstream.
* **Baris 55:** `await db.transaction((txn) async { ... })` adalah blok kritikal ACID (Atomicity, Consistency, Isolation, Durability). Jika aplikasi mengalami *crash* atau OS mematikan proses saat eksekusi berada di antara penulisan produk dan penulisan outbox, transaksi di-*rollback* secara otomatis oleh database engine. Tidak akan terjadi kondisi outbox yatim piatu (*orphaned outbox*) atau mutasi data tanpa riwayat antrean sinkronisasi.
* **Baris 63 & 81:** `conflictAlgorithm: ConflictAlgorithm.replace` mengeksekusi operasi upsert di level SQLite murni jika identitas record mengalami benturan kunci (*primary key collision*).

---

## SEKSI 09 — STUDI KASUS NYATA
**Skenario Produksi Enterprise:**  
Aplikasi Point of Sale (POS) & Inventaris Gudang Skala Multi-Cabang (*Enterprise Warehouse & Dispatch*).
* **Kendala:** Petugas gudang beroperasi di dalam bunker beton atau kontainer kargo tanpa sinyal seluler selama berjam-jam.
* **Kebutuhan Sistem:**
  1. Petugas harus tetap bisa mencatat perubahan stok barang (*Stock Adjustment*).
  2. Saat aplikasi ditutup paksa (*force-closed*) atau baterai habis di tengah proses mutasi, integritas data harus 100% terjaga tanpa duplikasi transaksi.
  3. Ketika perangkat kembali mendapat koneksi internet, sistem harus memproses sinkronisasi secara tertib (*FIFO per Aggregate ID*), menyelesaikan konflik dengan sistem ERP pusat secara probabilistik menggunakan *Timestamp Verification*, serta memperbarui UI secara mulus.

---

## SEKSI 10 — IMPLEMENTASI KASUS NYATA & HANDS-ON PRODUCTION CODE

Arsitektur produksi lengkap berikut mengimplementasikan `sqflite` dengan *Outbox Pattern*, *Network Connectivity Watcher*, *Exponential Backoff*, dan *Reactive Stream*.

```dart
// lib/features/inventory/data/inventory_offline_repository.dart
import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'package:sqflite/sqflite.dart';
import 'package:http/http.dart' as http;

// ---------------------------------------------------------
// DOMAIN MODELS & TYPEDEFS
// ---------------------------------------------------------
enum SyncState { synced, dirty, tombstone }

class InventoryItem {
  final String id;
  final String sku;
  final int quantity;
  final int localUpdatedAt;
  final SyncState syncState;

  const InventoryItem({
    required this.id,
    required this.sku,
    required this.quantity,
    required this.localUpdatedAt,
    required this.syncState,
  });

  Map<String, dynamic> toMap() => {
    'id': id,
    'sku': sku,
    'quantity': quantity,
    'local_updated_at': localUpdatedAt,
    'sync_state': syncState.name,
  };

  factory InventoryItem.fromMap(Map<String, dynamic> map) => InventoryItem(
    id: map['id'] as String,
    sku: map['sku'] as String,
    quantity: map['quantity'] as int,
    localUpdatedAt: map['local_updated_at'] as int,
    syncState: SyncState.values.byName(map['sync_state'] as String),
  );
}

// ---------------------------------------------------------
// PRODUCTION OFFLINE REPOSITORY & SYNC ENGINE
// ---------------------------------------------------------
class ProductionInventoryRepository {
  final Database db;
  final http.Client httpClient;
  final String remoteEndpoint;
  
  // StreamController untuk menyediakan Reactive Single Source of Truth ke UI
  final _inventoryStreamController = StreamController<List<InventoryItem>>.broadcast();

  bool _isSyncing = false;
  Timer? _pollingTimer;

  ProductionInventoryRepository({
    required this.db,
    required this.httpClient,
    required this.remoteEndpoint,
  }) {
    _initStream();
    _startSyncLoop();
  }

  Stream<List<InventoryItem>> watchInventory() => _inventoryStreamController.stream;

  Future<void> _initStream() async {
    await _notifyLocalSubscribers();
  }

  Future<void> _notifyLocalSubscribers() async {
    final results = await db.query(
      'inventory',
      where: 'sync_state != ?',
      whereArgs: [SyncState.tombstone.name],
      orderBy: 'sku ASC',
    );
    final items = results.map((m) => InventoryItem.fromMap(m)).toList();
    _inventoryStreamController.add(items);
  }

  // Optimistic UI Mutation Write
  Future<void> updateQuantityOptimistic({
    required String id,
    required String sku,
    required int newQuantity,
  }) async {
    final now = DateTime.now().millisecondsSinceEpoch;
    final item = InventoryItem(
      id: id,
      sku: sku,
      quantity: newQuantity,
      localUpdatedAt: now,
      syncState: SyncState.dirty,
    );

    await db.transaction((txn) async {
      // 1. Tulis Entitas ke Database Lokal (Immediate SSOT Update)
      await txn.insert(
        'inventory',
        item.toMap(),
        conflictAlgorithm: ConflictAlgorithm.replace,
      );

      // 2. Tulis Payload ke Outbox
      final payload = jsonEncode({
        'id': id,
        'sku': sku,
        'quantity': newQuantity,
        'client_timestamp': now,
      });

      await txn.insert(
        'outbox_queue',
        {
          'id': 'job_${id}_$now',
          'aggregate_id': id,
          'action': 'UPDATE_STOCK',
          'payload': payload,
          'created_at': now,
          'attempts': 0,
          'next_retry_at': 0,
        },
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    });

    // 3. Picu notifikasi UI lokal instan tanpa menunggu jaringan
    await _notifyLocalSubscribers();

    // 4. Picu background sync attempt secara asinkron
    unawaited(processOutboxQueue());
  }

  // Engine Sinkronisasi Outbox
  void _startSyncLoop() {
    _pollingTimer = Timer.periodic(const Duration(seconds: 15), (_) {
      unawaited(processOutboxQueue());
    });
  }

  Future<void> processOutboxQueue() async {
    if (_isSyncing) return;
    _isSyncing = true;

    try {
      final now = DateTime.now().millisecondsSinceEpoch;
      
      // Ambil transaksi yang sudah waktunya dieksekusi (memenuhi syarat Exponential Backoff)
      final jobs = await db.query(
        'outbox_queue',
        where: 'next_retry_at <= ?',
        whereArgs: [now],
        orderBy: 'created_at ASC',
        limit: 10,
      );

      for (final job in jobs) {
        final jobId = job['id'] as String;
        final aggregateId = job['aggregate_id'] as String;
        final payloadString = job['payload'] as String;
        final attempts = job['attempts'] as int;

        bool success = false;
        try {
          final response = await httpClient.post(
            Uri.parse('$remoteEndpoint/sync-stock'),
            headers: {'Content-Type': 'application/json'},
            body: payloadString,
          ).timeout(const Duration(seconds: 8));

          if (response.statusCode >= 200 && response.statusCode < 300) {
            success = true;
            final remoteData = jsonDecode(response.body) as Map<String, dynamic>;
            await _reconcileSuccess(jobId, aggregateId, remoteData);
          } else if (response.statusCode == 409) {
            // Konflik Terdeteksi: Server Menolak karena Timestamp Client Usang
            success = true; // Selesaikan job dari queue, delegasikan ke rekonsiliasi
            final conflictData = jsonDecode(response.body) as Map<String, dynamic>;
            await _resolveConflict(jobId, aggregateId, conflictData);
          } else {
            // Server Error Terkelola (5xx)
            await _scheduleRetry(jobId, attempts);
          }
        } catch (_) {
          // SocketException, TimeoutException, Network Drop
          await _scheduleRetry(jobId, attempts);
        }
      }
    } finally {
      _isSyncing = false;
    }
  }

  Future<void> _reconcileSuccess(
    String jobId,
    String aggregateId,
    Map<String, dynamic> remoteData,
  ) async {
    await db.transaction((txn) async {
      // Hapus dari Outbox
      await txn.delete('outbox_queue', where: 'id = ?', whereArgs: [jobId]);

      // Ubah status lokal menjadi Synced
      await txn.update(
        'inventory',
        {
          'sync_state': SyncState.synced.name,
          'local_updated_at': remoteData['server_timestamp'] as int,
        },
        where: 'id = ?',
        whereArgs: [aggregateId],
      );
    });
    await _notifyLocalSubscribers();
  }

  Future<void> _resolveConflict(
    String jobId,
    String aggregateId,
    Map<String, dynamic> conflictData,
  ) async {
    // Strategi Conflict Resolution: Remote-Wins (Server Canonical State)
    final remoteQuantity = conflictData['canonical_quantity'] as int;
    final serverTimestamp = conflictData['server_timestamp'] as int;

    await db.transaction((txn) async {
      await txn.delete('outbox_queue', where: 'id = ?', whereArgs: [jobId]);

      await txn.update(
        'inventory',
        {
          'quantity': remoteQuantity,
          'sync_state': SyncState.synced.name,
          'local_updated_at': serverTimestamp,
        },
        where: 'id = ?',
        whereArgs: [aggregateId],
      );
    });

    await _notifyLocalSubscribers();
  }

  Future<void> _scheduleRetry(String jobId, int currentAttempts) async {
    final nextAttempt = currentAttempts + 1;
    // Algoritma Full Jitter Exponential Backoff: min(60, 2^attempts) + random jitter
    final backoffSeconds = min(60, pow(2, nextAttempt).toInt());
    final jitter = Random().nextInt(3);
    final nextRetryAt = DateTime.now().millisecondsSinceEpoch + ((backoffSeconds + jitter) * 1000);

    await db.update(
      'outbox_queue',
      {
        'attempts': nextAttempt,
        'next_retry_at': nextRetryAt,
      },
      where: 'id = ?',
      whereArgs: [jobId],
    );
  }

  void dispose() {
    _pollingTimer?.cancel();
    _inventoryStreamController.close();
  }
}
```

---

## SEKSI 11 — TRADE-OFFS & ANALISIS PERBANDINGAN KOMPARATIF

| Parameter | SQLite Raw (`sqflite`) | Reactive ORM (`drift`) | Key-Value (`Hive` / `Isar`) | Secure Storage (`Keychain/Keystore`) |
| :--- | :--- | :--- | :--- | :--- |
| **Model Data** | Relasional Murni (SQL) | Tipe-Aman Relasional (Dart ORM) | Dokumen / NoSQL Objek | Key-Value Sederhana |
| **Kecepatan Write** | Sedang (Disk-bound) | Sedang (Terkonversi ke SQLite) | Sangat Cepat (In-Memory Index) | Sangat Rendah (Hardware Encrypted) |
| **Query Complexity** | Sangat Tinggi (JOIN, Aggregate) | Sangat Tinggi (Query Builder Tipe-Aman) | Terbatas (Filter Sederhana) | Tidak Bisa Query (Get By Key Saja) |
| **Memory Footprint** | Rendah (Lazy Paging) | Rendah (Optimized Cursor) | Cenderung Tinggi (Box In-Memory) | Sangat Minimal |
| **Safety / Threading** | Database Lock Overhead | Static Compile Checks | Rentan Korupsi jika Crash Ekstrem | OS Hardware Protected |
| **Use-Case Optimal** | Arsitektur Enterprise Kompleks | Standard Flutter Clean Architecture | Caching Sederhana, UI State Prefs | Token JWT, Kunci Enkripsi DB |

---

## SEKSI 12 — EDGE CASES & PITFALLS (Failure Modes & Mitigation)

1. **Kasus Database Locking Saat Transaksi Berat:**
   * *Problem:* Melakukan kueri baca panjang di isolate utama saat transaksi penulisan outbox berjalan dapat memicu galat SQLite `database is locked` (SQLITE_BUSY).
   * *Mitigasi:* Aktifkan WAL (*Write-Ahead Logging*) mode pada SQLite saat proses booting:
     ```dart
     await db.rawQuery('PRAGMA journal_mode=WAL;');
     ```
2. **Kondisi Jam Perangkat Mundur / Maju (Clock Skew Invalidation):**
   * *Problem:* Pengguna mengubah tanggal jam di pengaturan perangkat untuk mengecoh lisensi, menyebabkan nilai `created_at` pada outbox rusak.
   * *Mitigasi:* Jangan mengandalkan `DateTime.now()` perangkat untuk resolusi konflik final. Gunakan *Lamport Timestamps* lokal (integer monotonic counter increment) atau delegasikan evaluasi waktu akhir secara eksklusif ke Remote Server.
3. **Ghost Writes Pasca Un-stuck Outbox:**
   * *Problem:* Job A dikirim ke server namun koneksi terputus sesaat sebelum client menerima response status 200. Client mengira request gagal lalu mengulang pengiriman job yang sama (At-Least-Once Delivery).
   * *Mitigasi:* Server **wajib** mengimplementasikan mekanisme *Idempotency-Key* menggunakan `jobId` yang dihasilkan oleh client. Jika ID idempotensi terdeteksi sudah pernah diproses di server, server membalas dengan status 200 tanpa menduplikasi modifikasi entitas.

---

## SEKSI 13 — COMMON MISTAKES & CARA MENGHINDARINYA

### 1. Menunggu Jaringan Selesai Sebelum Menulis ke Database Lokal
```dart
// SALAH: Mengabaikan esensi Offline-First
Future<void> updateItem(Item item) async {
  await api.update(item);      // Gagal saat offline!
  await localDb.save(item);
}

// BENAR: Tulis lokal, jadwalkan sinkronisasi
Future<void> updateItem(Item item) async {
  await localDb.saveWithOutbox(item); // Langsung sukses secara lokal
  unawaited(syncEngine.trigger());     // Berjalan di latar belakang
}
```

### 2. Kebocoran Memori (Memory Leaks) pada Stream Kontinu
Membuka listener stream SQLite tanpa menutupnya saat widget di-unmount. Hindari membuat stream baru di dalam method `build()`. Gunakan `StreamController` di repository layer yang dihubungkan ke siklus hidup *State Management* (Bloc/Riverpod), lalu dipasangkan dengan operator `autoDispose` atau method `close()`.

---

## SEKSI 14 — BEST PRACTICES & KONVENSI INDUSTRI

1. **UUIDv4 / CUID Client-Side Generation:** Hindari penggunaan integer Auto-Increment SQLite (`INTEGER PRIMARY KEY AUTOINCREMENT`) sebagai ID utama untuk entitas yang perlu disinkronkan. Gunakan **UUID v4** atau **CUID** yang digenerasikan secara lokal pada perangkat. Ini memungkinkan pembuatan relasi antar tabel (seperti `Order` -> `OrderItems`) saat offline tanpa harus menunggu alokasi ID dari remote server.
2. **FIFO Execution Per Aggregation Root:** Jangan memproses *Outbox* secara paralel untuk aggregate ID yang sama. Jika entitas `item_123` diubah statusnya menjadi `DRAFT`, lalu `PUBLISHED`, eksekusi paralel yang mengalami latensi acak dapat menyebabkan pembaruan `DRAFT` sampai di server setelah `PUBLISHED`, menimpa kondisi akhir. Selalu gunakan penjaminan urutan berbasis antrean terurut (`ORDER BY created_at ASC`) per aggregate.

---

## SEKSI 15 — OPTIMASI KINERJA & EFISIENSI MEMORI/JARINGAN

1. **SQLite Pagination Menggunakan Keyset Pagination (Bukan OFFSET):**
   Penggunaan `OFFSET` memaksa SQLite memindai seluruh record sebelumnya, menyebabkan degradasi performa $O(N)$.
   ```sql
   -- HINDARI (Lambat saat offset mencapai puluhan ribu record):
   SELECT * FROM inventory LIMIT 50 OFFSET 10000;

   -- IMPLEMENTASIKAN (Keyset Pagination, O(log N)):
   SELECT * FROM inventory 
   WHERE (local_updated_at, id) < (:last_timestamp, :last_id) 
   ORDER BY local_updated_at DESC, id DESC 
   LIMIT 50;
   ```
2. **Batching Upstream Sync Payloads:**
   Daripada mengirimkan 100 HTTP Request terpisah untuk 100 item mutasi outbox, bungkus data dalam satu payload array mutasi (`POST /api/v1/sync/batch`) untuk mengurangi *TCP Handshake*, alokasi radio seluler baterai, dan *overhead* enkripsi TLS.

---

## SEKSI 16 — KEAMANAN & HARDENING

1. **Database Encryption at Rest Menggunakan SQLCipher:**
   Database SQLite mentah menyimpan data dalam format *plaintext* yang mudah dibaca via *rooted device* atau *ADB extraction*. Integrasikan `sqflite_sqlcipher`. Kunci enkripsi database tidak boleh di-*hardcode* di dalam kode Dart, melainkan digenerasikan secara acak saat instalasi pertama, lalu disimpan di Secure Hardware Module perangkat:
   * **Android:** Android Keystore System (dienkripsi via AES-256 GCM).
   * **iOS:** Secure Enclave / Keychain Services.

```dart
// lib/core/security/secure_key_manager.dart
import 'dart:convert';
import 'dart:math';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class SecureKeyManager {
  static const _keyAlias = 'sqlite_aes_key';
  final FlutterSecureStorage _storage;

  SecureKeyManager(this._storage);

  Future<String> getDatabaseEncryptionKey() async {
    var key = await _storage.read(key: _keyAlias);
    if (key == null) {
      final randomValues = List<int>.generate(32, (i) => Random.secure().nextInt(256));
      key = base64UrlEncode(randomValues);
      await _storage.write(key: _keyAlias, value: key);
    }
    return key;
  }
}
```

---

## SEKSI 17 — OBSERVABILITAS, TELEMETRI & DEBUGGING

Sistem *Offline-First* membutuhkan metrik observabilitas khusus untuk melacak *Lag Consistency*.

```
Metrik Observabilitas Penting:
1. Outbox Queue Depth  : Jumlah antrean outbox yang belum disinkronkan.
2. Mutation Lag Time   : Durasi waktu sejak data dimutasi lokal hingga diakui oleh remote backend.
3. Sync Conflict Rate  : Persentase mutasi yang memicu HTTP 409 Conflict.
4. Database Disk Usage : Ukuran file .db di storage lokal klien.
```

Untuk melacak performa kueri yang mengalami degradasi performa, gunakan SQL `EXPLAIN QUERY PLAN` pada kueri kompleks untuk memastikan SQLite menggunakan indeks (*Index Scan*) alih-alih pemindaian menyeluruh (*Table Scan*):
```dart
Future<void> debugQueryPerformance(Database db, String sql) async {
  final plan = await db.rawQuery('EXPLAIN QUERY PLAN $sql');
  for (final row in plan) {
    print('SQL Execution Plan: ${row['detail']}');
  }
}
```

---

## SEKSI 18 — RINGKASAN & CHEAT SHEET

1. **SSOT Rule:** UI hanya mendengarkan Database Lokal. UI tidak pernah mengonsumsi respons API jaringan secara langsung.
2. **Atomic Writes:** Semua mutasi lokal WAJIB berada di dalam blok `db.transaction` bersama dengan penulisan record ke antrean outbox.
3. **No Direct Delete:** Gunakan teknik *Tombstoning* (`sync_state = 'tombstone'`) saat menghapus data secara offline agar niat penghapusan dapat dikirimkan ke server.
4. **Idempotency:** Backend harus memproses setiap mutasi outbox secara idempoten menggunakan `jobId` unik berbasis UUIDv4.
5. **Backoff & Jitter:** Kegagalan pengiriman outbox harus ditangani dengan *Exponential Backoff* yang dilengkapi *Random Jitter* guna mencegah terjadinya fenomena *Thundering Herd Problem* pada infrastruktur backend saat konektivitas kembali pulih.

---

## SEKSI 19 — KUIS EVALUASI PEMAHAMAN

### Soal 1
Mengapa arsitektur *Offline-First* menuntut agar semua ID entitas baru digenerasikan di sisi klien (menggunakan UUID/CUID) alih-alih mengandalkan `AUTOINCREMENT` dari database server remote?
* A) Karena UUID mengonsumsi ruang penyimpanan lebih sedikit di dalam SQLite dibandingkan tipe data integer.
* B) Untuk memungkinkan instansiasi entitas dan pembuatan relasi antar tabel secara offline tanpa memerlukan latensi *roundtrip* jaringan untuk memperoleh kunci primer resmi.
* C) Karena SQLite secara internal tidak mendukung kolom auto-increment pada primary key.
* D) Supaya performa kueri `SELECT` meningkat drastis saat proses pengurutan data di database.

### Soal 2
Masalah sistemik apa yang terjadi jika Anda tidak menggunakan `PRAGMA journal_mode=WAL;` pada arsitektur SQLite yang aktif melakukan operasi *read* dan *write* secara bersamaan?
* A) Database lokal akan terhapus otomatis saat sistem kehabisan memori.
* B) Operasi *write* dari *Background Sync Engine* akan memblokir operasi *read* dari thread UI, menyebabkan terjadinya frame drop (jank) atau exception `SQLITE_BUSY`.
* C) Seluruh kueri SQL akan ditolak dan menghasilkan respons data korup.
* D) Enkripsi database SQLCipher akan kehilangan kunci keamanannya.

### Soal 3
Perhatikan skenario berikut: Pengguna mengubah data produk secara lokal saat offline. Tiga jam kemudian saat tersambung ke jaringan, sinkronisasi memicu respons HTTP 409 Conflict karena data di server telah diperbarui oleh pengguna lain. Apa langkah mitigasi arsitektur terbaik untuk menjaga integritas data tanpa merusak UX pengguna lokal secara diam-diam?
* A) Menghapus database lokal secara langsung dan memaksa pengguna mengunduh seluruh data dari awal.
* B) Men