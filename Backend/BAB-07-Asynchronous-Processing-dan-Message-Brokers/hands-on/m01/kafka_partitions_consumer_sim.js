/**
 * SIMULATOR: KAFKA PARTITIONING ENGINE, CONSUMER GROUPS & REBALANCING
 * Modul 01: Message Queues vs Event Streaming (RabbitMQ vs Apache Kafka)
 *
 * Mendemonstrasikan:
 * 1. Mekanisme Append-Only Log Partitioning dengan Hash Partitioner.
 * 2. Jaminan keterurutan kronologis pesan berdasarkan Partition Key.
 * 3. Pemetaan partisi ke Consumer Group workers.
 * 4. Uji kasus idle worker saat worker > partisi dan simulasi Rebalancing saat worker crash.
 *
 * Jalankan: node kafka_partitions_consumer_sim.js
 */

const crypto = require('crypto');

function hashKeyToPartition(key, totalPartitions) {
  if (!key) return 0;
  const hash = crypto.createHash('md5').update(String(key)).digest('hex');
  const intVal = parseInt(hash.substring(0, 8), 16);
  return intVal % totalPartitions;
}

// =========================================================================
// BAGIAN 1: SIMULATOR KAFKA TOPIC DENGAN MULTI-PARTISI APPEND-ONLY LOG
// =========================================================================

class KafkaTopic {
  constructor(name, partitionCount = 3) {
    this.name = name;
    this.partitionCount = partitionCount;
    this.partitions = [];
    for (let i = 0; i < partitionCount; i++) {
      this.partitions.push([]); // Array of { offset, key, payload, timestamp }
    }
  }

  produce(key, payload) {
    const partitionIndex = hashKeyToPartition(key, this.partitionCount);
    const partitionLog = this.partitions[partitionIndex];
    const offset = partitionLog.length;

    const record = {
      offset,
      partition: partitionIndex,
      key,
      payload,
      timestamp: Date.now()
    };

    partitionLog.push(record);
    return record;
  }
}

// =========================================================================
// BAGIAN 2: SIMULATOR CONSUMER GROUP & PARTITION ASSIGNMENT
// =========================================================================

class ConsumerGroup {
  constructor(groupId, topic) {
    this.groupId = groupId;
    this.topic = topic;
    this.consumers = []; // Array of { id, assignedPartitions: [] }
    this.committedOffsets = {}; // partitionIndex -> lastCommittedOffset
    for (let p = 0; p < topic.partitionCount; p++) {
      this.committedOffsets[p] = 0;
    }
  }

  registerConsumer(consumerId) {
    this.consumers.push({ id: consumerId, assignedPartitions: [] });
    this.rebalance();
  }

  unregisterConsumer(consumerId) {
    this.consumers = this.consumers.filter(c => c.id !== consumerId);
    this.rebalance();
  }

  // Algoritma Range / Round-Robin Assignment
  rebalance() {
    console.log(`\n🔄 [REBALANCE] Melakukan penyeimbangan partisi untuk group '${this.groupId}'...`);
    // Reset assignment
    this.consumers.forEach(c => c.assignedPartitions = []);

    if (this.consumers.length === 0) return;

    for (let p = 0; p < this.topic.partitionCount; p++) {
      if (p < this.consumers.length) {
        this.consumers[p].assignedPartitions.push(p);
      } else {
        // Jika partisi lebih banyak dari consumer, distribusikan secara modulo
        const targetConsumer = this.consumers[p % this.consumers.length];
        targetConsumer.assignedPartitions.push(p);
      }
    }

    this.consumers.forEach(c => {
      const partList = c.assignedPartitions.length > 0 ? c.assignedPartitions.join(', ') : 'IDLE (Tidak kebagian partisi)';
      console.log(`  👤 Consumer '${c.id}' mengelola Partisi: [${partList}]`);
    });
  }

  // Worker menarik pesan baru dari partisi yang ditugaskan
  poll() {
    const processedMessages = [];
    this.consumers.forEach(consumer => {
      consumer.assignedPartitions.forEach(partitionIndex => {
        const log = this.topic.partitions[partitionIndex];
        let currentOffset = this.committedOffsets[partitionIndex];

        while (currentOffset < log.length) {
          const record = log[currentOffset];
          processedMessages.push({
            consumerId: consumer.id,
            partition: partitionIndex,
            offset: record.offset,
            key: record.key,
            payload: record.payload
          });
          currentOffset++;
          this.committedOffsets[partitionIndex] = currentOffset; // Commit offset
        }
      });
    });
    return processedMessages;
  }
}

// =========================================================================
// BAGIAN 3: EKSEKUSI PENGUJIAN SKENARIO PRODUKSI
// =========================================================================

async function main() {
  console.log('='.repeat(75));
  console.log('SIMULASI: APACHE KAFKA PARTITIONS & CONSUMER GROUP REBALANCING');
  console.log('='.repeat(75));

  const orderTopic = new KafkaTopic('ecommerce-orders', 3);
  const group = new ConsumerGroup('fulfillment-service-group', orderTopic);

  console.log(`1. Mendaftarkan 3 Worker Consumer ke dalam Consumer Group:`);
  group.registerConsumer('Worker-Alpha');
  group.registerConsumer('Worker-Beta');
  group.registerConsumer('Worker-Gamma');

  console.log('\n' + '-'.repeat(75));
  console.log('2. Memproduksi Aliran Event Siklus Hidup Pesanan (Order Lifecycle Events)');
  console.log('-'.repeat(75));

  // Simulasi 3 Order berbeda dengan runtutan status sekuensial
  const orderEvents = [
    { key: 'ORD-101', status: 'ORDER_CREATED', amount: 450000 },
    { key: 'ORD-202', status: 'ORDER_CREATED', amount: 1200000 },
    { key: 'ORD-101', status: 'PAYMENT_RECEIVED', method: 'BCA_VA' },
    { key: 'ORD-303', status: 'ORDER_CREATED', amount: 75000 },
    { key: 'ORD-202', status: 'PAYMENT_RECEIVED', method: 'CREDIT_CARD' },
    { key: 'ORD-101', status: 'ORDER_PACKED', warehouse: 'JAKARTA_PUSAT' },
    { key: 'ORD-303', status: 'PAYMENT_TIMEOUT', reason: 'EXPIRED' },
    { key: 'ORD-202', status: 'ORDER_PACKED', warehouse: 'SURABAYA_TIMUR' },
    { key: 'ORD-101', status: 'ORDER_SHIPPED', courier: 'JNE_EXPRESS' },
    { key: 'ORD-202', status: 'ORDER_SHIPPED', courier: 'SICEPAT' }
  ];

  orderEvents.forEach(evt => {
    const record = orderTopic.produce(evt.key, evt);
    console.log(`[PRODUCE] Key: ${evt.key.padEnd(8)} -> Partisi #${record.partition}, Offset #${record.offset} : ${evt.status}`);
  });

  console.log('\n' + '-'.repeat(75));
  console.log('3. Consumer Group Menarik Pesanan (Polling & Processing)');
  console.log('-'.repeat(75));

  const messages = group.poll();
  messages.forEach(m => {
    console.log(`  [KONSUMSI] ${m.consumerId.padEnd(13)} memproses Partisi #${m.partition} (Offset #${m.offset}) : Key=${m.key} -> ${m.payload.status}`);
  });

  console.log('\n' + '-'.repeat(75));
  console.log('4. Uji Kasus Worker Berlebih (Worker > Partisi)');
  console.log('-'.repeat(75));
  console.log('Mendaftarkan Worker-Delta ke dalam cluster (Total Worker = 4, Total Partisi = 3)...');
  group.registerConsumer('Worker-Delta');

  console.log('\n' + '-'.repeat(75));
  console.log('5. Uji Kasus Crash Worker & Dynamic Rebalancing');
  console.log('-'.repeat(75));
  console.log('Worker-Beta tiba-tiba CRASH! Menghapus Worker-Beta dari cluster...');
  group.unregisterConsumer('Worker-Beta');

  // Kirim event tambahan pasca-crash
  console.log('\nMengirim event baru pasca rebalance:');
  const postCrashEvt = orderTopic.produce('ORD-101', { key: 'ORD-101', status: 'ORDER_DELIVERED', signature: 'Budi' });
  console.log(`[PRODUCE] Key: ORD-101 -> Partisi #${postCrashEvt.partition}, Offset #${postCrashEvt.offset} : ${postCrashEvt.payload.status}`);

  const postCrashMessages = group.poll();
  postCrashMessages.forEach(m => {
    console.log(`  [KONSUMSI PASCA-CRASH] ${m.consumerId} memproses: Key=${m.key} -> ${m.payload.status}`);
  });

  console.log('\n' + '='.repeat(75));
  console.log('KESIMPULAN: Urutan event per entitas order terjamin 100% konsisten sekuensial!');
  console.log('='.repeat(75));
}

main();
