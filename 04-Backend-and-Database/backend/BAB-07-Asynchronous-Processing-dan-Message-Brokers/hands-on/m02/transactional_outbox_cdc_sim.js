/**
 * SIMULATOR: TRANSACTIONAL OUTBOX, CDC RELAY, IDEMPOTENT CONSUMER & DLQ
 * Modul 02: Idempotent Consumers, Dead Letter Queues (DLQ), & Transactional Outbox
 *
 * Mendemonstrasikan:
 * 1. Transaksi Atomik Lokal Database (Order + Outbox Table).
 * 2. Pekerja CDC Relay yang membaca dan mempublikasikan event ke Message Broker.
 * 3. Idempotent Consumer yang kebal terhadap pengiriman duplikat pesan.
 * 4. Penanganan Poison Pill: Retry dengan Exponential Backoff dan pengalihan aman ke DLQ.
 *
 * Jalankan: node transactional_outbox_cdc_sim.js
 */

const crypto = require('crypto');

// =========================================================================
// BAGIAN 1: DATABASE DENGAN POLA TRANSACTIONAL OUTBOX
// =========================================================================

class MockTransactionalDatabase {
  constructor() {
    this.orders = new Map();
    this.outbox = [];
    this.processedEvents = new Set(); // Tabel deduplikasi
    this.balances = new Map([
      ['CUST-1', 5000000],
      ['CUST-2', 250000]
    ]);
  }

  // Menjalankan transaksi bisnis & penulisan outbox secara atomik
  createOrderTransaction(orderId, customerId, amount) {
    const balance = this.balances.get(customerId) || 0;
    if (balance < amount) {
      throw new Error(`Saldo tidak mencukupi untuk nasabah ${customerId} (Saldo: ${balance}, Butuh: ${amount})`);
    }

    // Eksekusi atomik
    this.balances.set(customerId, balance - amount);
    this.orders.set(orderId, { orderId, customerId, amount, status: 'CREATED', createdAt: new Date() });

    // Tulis ke Outbox Table pada transaksi yang sama
    const outboxEvent = {
      eventId: `EVT-${crypto.randomUUID().substring(0, 8)}`,
      aggregateType: 'Order',
      aggregateId: orderId,
      eventType: 'ORDER_PLACED',
      payload: { orderId, customerId, amount },
      status: 'PENDING',
      createdAt: Date.now()
    };
    this.outbox.push(outboxEvent);

    return outboxEvent;
  }
}

// =========================================================================
// BAGIAN 2: BROKER & ANTRIAN (MAIN TOPIC & DEAD LETTER QUEUE)
// =========================================================================

class MockMessageBroker {
  constructor() {
    this.topic = [];
    this.deadLetterQueue = [];
  }

  publish(event) {
    this.topic.push(event);
  }

  sendToDLQ(event, reason) {
    this.deadLetterQueue.push({
      ...event,
      failedAt: Date.now(),
      failureReason: reason
    });
  }
}

// =========================================================================
// BAGIAN 3: CDC OUTBOX RELAY WORKER
// =========================================================================

class CDCOutboxRelay {
  constructor(db, broker) {
    this.db = db;
    this.broker = broker;
  }

  relayPendingEvents() {
    let relayedCount = 0;
    for (const event of this.db.outbox) {
      if (event.status === 'PENDING') {
        this.broker.publish(event);
        event.status = 'PUBLISHED';
        relayedCount++;
      }
    }
    return relayedCount;
  }
}

// =========================================================================
// BAGIAN 4: IDEMPOTENT CONSUMER DENGAN RETRY & DEAD LETTER QUEUE
// =========================================================================

class FulfillmentConsumerService {
  constructor(db, broker) {
    this.db = db;
    this.broker = broker;
    this.processedCount = 0;
    this.duplicateSkipped = 0;
  }

  async processEventWithRetry(event, maxRetries = 3) {
    let attempt = 0;

    while (attempt <= maxRetries) {
      try {
        await this._handleEvent(event);
        return { success: true };
      } catch (err) {
        attempt++;
        console.warn(`    ⚠️ [Percobaan #${attempt} GAGAL] Event ${event.eventId}: ${err.message}`);

        if (attempt > maxRetries) {
          console.error(`    🚨 [MAX RETRY TERLAMPAUI] Mengirim event ${event.eventId} ke Dead Letter Queue (DLQ)...`);
          this.broker.sendToDLQ(event, err.message);
          return { success: false, dlq: true };
        }

        // Exponential backoff + jitter
        const backoffMs = 20 * Math.pow(2, attempt - 1) + Math.random() * 10;
        await new Promise(r => setTimeout(r, backoffMs));
      }
    }
  }

  async _handleEvent(event) {
    // 1. Cek Deduplikasi (Idempotensi)
    if (this.db.processedEvents.has(event.eventId)) {
      this.duplicateSkipped++;
      console.log(`    ⏭️ [IDEMPOTENT SKIP] Event ${event.eventId} sudah pernah diproses. Mengabaikan!`);
      return;
    }

    // Simulasi Poison Pill jika order ID memuat 'CORRUPTED'
    if (event.payload && event.payload.orderId && event.payload.orderId.includes('CORRUPTED')) {
      throw new Error(`Data payload corrupt / Poison pill terdeteksi pada ${event.payload.orderId}!`);
    }

    // 2. Eksekusi bisnis: Persiapan pengiriman barang di gudang
    await new Promise(r => setTimeout(r, 10)); // Simulasi komputasi

    // 3. Catat event ID ke tabel processed_events secara atomik
    this.db.processedEvents.add(event.eventId);
    this.processedCount++;
    console.log(`    ✅ [SUKSES DIPROSES] Order ${event.payload.orderId} (Rp ${event.payload.amount.toLocaleString('id-ID')}) siap dikirim.`);
  }
}

// =========================================================================
// BAGIAN 5: SIMULASI PENGUJIAN SKENARIO PRODUKSI LENGKAP
// =========================================================================

async function main() {
  console.log('='.repeat(75));
  console.log('SIMULASI: TRANSACTIONAL OUTBOX, DEDUP IDEMPOTENCY & DLQ PROTECTION');
  console.log('='.repeat(75));

  const db = new MockTransactionalDatabase();
  const broker = new MockMessageBroker();
  const cdcRelay = new CDCOutboxRelay(db, broker);
  const consumer = new FulfillmentConsumerService(db, broker);

  // 1. Transaksi Bisnis + Outbox
  console.log('1. Menjalankan Transaksi Bisnis (Pola Transactional Outbox)...');
  const event1 = db.createOrderTransaction('ORD-001', 'CUST-1', 750000);
  const event2 = db.createOrderTransaction('ORD-002', 'CUST-1', 1200000);
  console.log(`  Order ORD-001 & ORD-002 tersimpan di DB. Status Outbox: ${event1.status}`);

  // 2. CDC Relay membaca outbox dan meneruskan ke broker
  console.log('\n2. CDC Relay (Debezium Worker) memindai tabel outbox...');
  const count = cdcRelay.relayPendingEvents();
  console.log(`  Berhasil mempublikasikan ${count} event ke Message Broker Kafka.`);

  // 3. Simulasi Pengiriman Duplikat (Network Failure saat kirim ACK)
  console.log('\n3. Menguji Ketahanan Idempotensi (Pengiriman Duplikat Pesan Event-1)...');
  console.log('  Pengiriman Pertama:');
  await consumer.processEventWithRetry(event1);
  console.log('  Pengiriman Kedua (Duplikat akibat network retry broker):');
  await consumer.processEventWithRetry(event1);
  console.log('  Pengiriman Ketiga (Duplikat kedua):');
  await consumer.processEventWithRetry(event1);

  // 4. Proses Event Normal Kedua
  console.log('\n4. Memproses Event Normal Kedua (Event-2):');
  await consumer.processEventWithRetry(event2);

  // 5. Uji Kasus Pesan Beracun (Poison Pill) & Pengalihan ke DLQ
  console.log('\n5. Menguji Penanganan Poison Pill Message (Pesan Rusak):');
  const poisonEvent = {
    eventId: 'EVT-POISON-999',
    aggregateType: 'Order',
    aggregateId: 'ORD-CORRUPTED-666',
    eventType: 'ORDER_PLACED',
    payload: { orderId: 'ORD-CORRUPTED-666', customerId: 'CUST-1', amount: 0 }
  };
  await consumer.processEventWithRetry(poisonEvent, 3);

  // 6. Ringkasan Status Akhir
  console.log('\n' + '='.repeat(75));
  console.log('RINGKASAN STATUS SISTEM:');
  console.log('='.repeat(75));
  console.log(`- Total Pesan Berhasil Diproses : ${consumer.processedCount}`);
  console.log(`- Duplikat Dicegah (Idempotent) : ${consumer.duplicateSkipped}`);
  console.log(`- Pesan di Dead Letter Queue   : ${broker.deadLetterQueue.length}`);
  broker.deadLetterQueue.forEach((dlqItem, idx) => {
    console.log(`  [DLQ #${idx + 1}] ID: ${dlqItem.eventId} | Penyebab: ${dlqItem.failureReason}`);
  });
  console.log(`- Saldo Sisa CUST-1 di Database : Rp ${db.balances.get('CUST-1').toLocaleString('id-ID')}`);

  console.log('\n' + '='.repeat(75));
  console.log('SIMULASI BERHASIL: Sistem terbukti kebal dari duplikasi dan pesan beracun!');
  console.log('='.repeat(75));
}

main();
