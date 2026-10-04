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
