/**
 * LAB SIMULATION: At-Least-Once Delivery, Idempotent Consumer, & Dead Letter Queue (DLQ)
 * 
 * Skenario:
 * 1. Pesan valid dikirim 2x karena timeout ACK -> Idempotent Consumer mencegah double billing.
 * 2. Pesan rusak (Poison Pill) dicoba 3x -> Gagal terus -> Dialihkan ke DLQ (antrian karantina).
 */

class PaymentServiceSimulator {
  constructor() {
    this.userBalances = { "USER-100": 500000 };
    this.idempotencyStore = new Map(); // Simpan key yang sudah sukses diproses
    this.deadLetterQueue = [];
    this.maxRetries = 3;
  }

  processPaymentMessage(message) {
    const { idempotencyKey, userId, amount, isCorrupted, retryCount = 0 } = message;

    console.log(`\n📥 [Worker] Menerima Pesan (Key: ${idempotencyKey}, Retry: ${retryCount})`);

    // 1. CEK IDEMPOTENCY KEY
    if (this.idempotencyStore.has(idempotencyKey)) {
      const priorResult = this.idempotencyStore.get(idempotencyKey);
      console.log(`⚠️  [DEDUPLIKASI] Pesan duplikat terdeteksi! Key "${idempotencyKey}" sudah diproses pada ${priorResult.processedAt}.`);
      console.log(`⏭️  Mengabaikan pemotongan saldo. Mengembalikan ACK sukses.`);
      return { status: "ACK_DUPLICATE_SKIPPED" };
    }

    // 2. EKSEKUSI BISNIS DENGAN SIMULASI ERROR / POISON PILL
    try {
      if (isCorrupted) {
        throw new Error("SyntaxError: JSON malformed / Missing field 'cardNumber'!");
      }

      // Validasi Saldo
      if (this.userBalances[userId] < amount) {
        throw new Error("Insufficient funds");
      }

      // Potong Saldo
      this.userBalances[userId] -= amount;

      // Catat Idempotency Key secara atomik
      this.idempotencyStore.set(idempotencyKey, {
        userId,
        amount,
        processedAt: new Date().toISOString()
      });

      console.log(`✅ [SUKSES] Saldo ${userId} dipotong Rp ${amount.toLocaleString('id-ID')}. Sisa Saldo: Rp ${this.userBalances[userId].toLocaleString('id-ID')}`);
      return { status: "ACK_SUCCESS" };

    } catch (err) {
      console.error(`❌ [ERROR] Gagal memproses pesan: ${err.message}`);

      // 3. LOGIKA RETRY & DEAD LETTER QUEUE (DLQ)
      if (retryCount + 1 >= this.maxRetries) {
        console.log(`🚨 [DLQ ROUTING] Pesan gagal mencapai batas maksimum (${this.maxRetries}x). Memindahkan ke Dead Letter Queue!`);
        this.deadLetterQueue.push({
          message,
          error: err.message,
          failedAt: new Date().toISOString()
        });
        return { status: "MOVED_TO_DLQ" };
      } else {
        const nextRetry = retryCount + 1;
        const backoffMs = Math.pow(2, nextRetry) * 100; // Exponential backoff simulasi
        console.log(`🔄 [RETRY] Menjadwalkan retry #${nextRetry} setelah ${backoffMs}ms backoff...`);
        message.retryCount = nextRetry;
        return this.processPaymentMessage(message); // Rekursif simulasi retry
      }
    }
  }
}

const service = new PaymentServiceSimulator();

console.log("===================================================================");
console.log("🛠️  PENGUJIAN 1: AT-LEAST-ONCE DELIVERY & IDEMPOTENCY KEY");
console.log("===================================================================");
const normalPayment = {
  idempotencyKey: "TRX-PAY-202609-001",
  userId: "USER-100",
  amount: 75000,
  isCorrupted: false
};

// Pengiriman pertama (sukses)
service.processPaymentMessage(normalPayment);

// Pengiriman kedua (duplikat akibat retry jaringan / timeout ACK)
console.log("\n--- Jaringan putus sesaat, Producer mengirim ulang pesan yang sama ---");
service.processPaymentMessage(normalPayment);

console.log("\n===================================================================");
console.log("🛠️  PENGUJIAN 2: POISON PILL & DEAD LETTER QUEUE (DLQ)");
console.log("===================================================================");
const poisonedPayment = {
  idempotencyKey: "TRX-PAY-202609-BAD-DATA",
  userId: "USER-100",
  amount: 20000,
  isCorrupted: true // Data rusak permanen
};

service.processPaymentMessage(poisonedPayment);

console.log("\n--- Status Inspeksi Dead Letter Queue (DLQ) ---");
console.log(`Total Pesan di DLQ: ${service.deadLetterQueue.length}`);
console.log(JSON.stringify(service.deadLetterQueue, null, 2));

console.log("\n Kesimpulan:");
console.log("1. Idempotency Key mencegah pemotongan ganda meski pesan dikirim berulang kali.");
console.log("2. DLQ mengisolasi data rusak (poison pill) sehingga tidak menyumbat antrian utama.");
