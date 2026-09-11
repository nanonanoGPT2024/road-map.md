/**
 * LAB SIMULATION: Message Queue (RabbitMQ Style) vs Event Stream (Kafka Style)
 * 
 * Tujuan:
 * 1. Membuktikan sifat destruktif Message Queue (pesan terhapus setelah di-ACK).
 * 2. Membuktikan sifat persistensi Append-Only Log Event Stream (bisa di-replay oleh Consumer Group berbeda).
 */

console.log("===================================================================");
console.log("🛠️  SIMULASI 1: MESSAGE QUEUE (RABBITMQ STYLE - SMART BROKER)");
console.log("===================================================================\n");

class SimpleMessageQueue {
  constructor(name) {
    this.name = name;
    this.queue = [];
  }

  publish(message) {
    this.queue.push(message);
    console.log(`[Queue: ${this.name}] Pesan Masuk -> "${message.id}: ${message.data}" (Queue Size: ${this.queue.length})`);
  }

  consume(workerName) {
    if (this.queue.length === 0) {
      console.log(`[Queue: ${this.name}] ${workerName} mencoba membaca: Antrian Kosong!`);
      return null;
    }
    const message = this.queue.shift(); // FIFO & Destructive!
    console.log(`[Queue: ${this.name}] ${workerName} memproses & ACK: "${message.id}: ${message.data}" (Pesan DIHAPUS dari broker, sisa antrian: ${this.queue.length})`);
    return message;
  }
}

const emailQueue = new SimpleMessageQueue("email_tasks");
emailQueue.publish({ id: "MSG-1", data: "Kirim email aktivasi user #1" });
emailQueue.publish({ id: "MSG-2", data: "Kirim email invoice order #101" });
emailQueue.publish({ id: "MSG-3", data: "Kirim email reset password #42" });

console.log("\n--- Worker 1 Mengonsumsi Antrian ---");
emailQueue.consume("Worker-1");
emailQueue.consume("Worker-1");
emailQueue.consume("Worker-1");

console.log("\n--- Worker 2 Datang Belakangan Ingin Membaca Ulang Data Kemarin ---");
emailQueue.consume("Worker-2 (Auditor)");
console.log("⚠️  Pesan pada Message Queue hilang selamanya setelah dikonsumsi!\n");


console.log("===================================================================");
console.log("🛠️  SIMULASI 2: EVENT STREAM (APACHE KAFKA STYLE - COMMIT LOG)");
console.log("===================================================================\n");

class KafkaPartitionLog {
  constructor(topicName, partitionId) {
    this.topicName = topicName;
    this.partitionId = partitionId;
    this.log = []; // Append-only immutable array
  }

  append(key, value) {
    const offset = this.log.length;
    const record = { offset, key, value, timestamp: Date.now() };
    this.log.push(record);
    console.log(`[Kafka Topic: ${this.topicName}|P${this.partitionId}] Record Ditulis ke Offset #${offset} -> Key: ${key}, Event: ${value}`);
    return offset;
  }

  readFrom(offset, limit = 5) {
    return this.log.slice(offset, offset + limit);
  }
}

class KafkaConsumer {
  constructor(consumerGroupId, consumerName, partition) {
    this.consumerGroupId = consumerGroupId;
    this.consumerName = consumerName;
    this.partition = partition;
    this.currentOffset = 0; // Smart Consumer melacak posisinya sendiri
  }

  poll() {
    const records = this.partition.readFrom(this.currentOffset, 10);
    if (records.length === 0) {
      console.log(`[Group: ${this.consumerGroupId}] ${this.consumerName}: Tidak ada event baru (Current Offset: ${this.currentOffset})`);
      return;
    }

    for (const record of records) {
      console.log(`[Group: ${this.consumerGroupId}] ${this.consumerName} membaca Offset #${record.offset} -> [${record.key}] ${record.value}`);
      this.currentOffset = record.offset + 1; // Geser offset ke depan
    }
  }

  replayFrom(targetOffset) {
    console.log(`\n⏪ [Group: ${this.consumerGroupId}] Me-replay event dari Offset #${targetOffset}...`);
    this.currentOffset = targetOffset;
    this.poll();
  }
}

const orderTopicPartition0 = new KafkaPartitionLog("order_events", 0);
orderTopicPartition0.append("USER-88", "OrderCreated { total: Rp 250.000 }");
orderTopicPartition0.append("USER-99", "PaymentReceived { status: SUCCESS }");
orderTopicPartition0.append("USER-88", "OrderShipped { courier: JNE }");

console.log("\n--- Consumer Group 1: Fulfillment Service ---");
const fulfillmentConsumer = new KafkaConsumer("fulfillment-group", "Service-A", orderTopicPartition0);
fulfillmentConsumer.poll();

console.log("\n--- Consumer Group 2: Financial Audit Service (Baru Deploy Hari Ini) ---");
const auditConsumer = new KafkaConsumer("audit-analytics-group", "Analytics-Worker", orderTopicPartition0);
auditConsumer.poll(); // Membaca dari Offset 0 tanpa terpengaruh Consumer Group 1!

// Demonstrasi Replay
fulfillmentConsumer.replayFrom(1);

console.log("\n Kesimpulan:");
console.log("1. RabbitMQ Queue menghapus data setelah dikonsumsi (Zero Replay, Low Storage).");
console.log("2. Kafka Log menyimpan data secara append-only di disk sehingga multi-consumer & data replay dapat dilakukan secara instan!");
