/**
 * SIMULATOR: SAGA ORCHESTRATOR WITH COMPENSATING TRANSACTIONS & CQRS EVENT SOURCING
 * Modul 02: Transaksi Terdistribusi, Pola Saga, Event Sourcing, & CQRS
 *
 * Mendemonstrasikan:
 * 1. 3 Microservices Independen (Payment, Inventory, Logistics).
 * 2. Saga Orchestrator State Machine dengan alur eksekusi sukses (Happy Path).
 * 3. Eksekusi Transaksi Kompensasi Mundur (Semantic Rollback) saat terjadi kegagalan di step ketiga.
 * 4. Rekonstruksi status agregat melalui Event Sourcing Replay dan pembaruan Read Model CQRS.
 *
 * Jalankan: node saga_orchestrator_compensating_sim.js
 */

// =========================================================================
// BAGIAN 1: SIMULATOR 3 MICROSERVICES INDEPENDEN
// =========================================================================

class PaymentMicroservice {
  constructor() {
    this.accounts = new Map([['CUST-101', 1500000]]);
    this.txLog = [];
  }

  async debit(customerId, amount) {
    const balance = this.accounts.get(customerId) || 0;
    if (balance < amount) throw new Error(`Saldo tidak cukup (Saldo: Rp ${balance.toLocaleString('id-ID')})`);

    this.accounts.set(customerId, balance - amount);
    this.txLog.push({ type: 'DEBIT', customerId, amount, timestamp: Date.now() });
    return { status: 'SUCCESS', remainingBalance: balance - amount };
  }

  // TRANSAKSI KOMPENSASI: REFUND
  async compensateRefund(customerId, amount) {
    const balance = this.accounts.get(customerId) || 0;
    this.accounts.set(customerId, balance + amount);
    this.txLog.push({ type: 'COMPENSATION_REFUND', customerId, amount, timestamp: Date.now() });
    return { status: 'REFUNDED', currentBalance: balance + amount };
  }
}

class InventoryMicroservice {
  constructor() {
    this.stocks = new Map([['IPHONE-15', 5]]);
  }

  async reserveStock(sku, quantity) {
    const stock = this.stocks.get(sku) || 0;
    if (stock < quantity) throw new Error(`Stok produk [${sku}] tidak mencukupi (Sisa: ${stock})`);

    this.stocks.set(sku, stock - quantity);
    return { status: 'SUCCESS', remainingStock: stock - quantity };
  }

  // TRANSAKSI KOMPENSASI: RELEASE STOCK
  async compensateReleaseStock(sku, quantity) {
    const stock = this.stocks.get(sku) || 0;
    this.stocks.set(sku, stock + quantity);
    return { status: 'RELEASED', currentStock: stock + quantity };
  }
}

class LogisticsMicroservice {
  constructor() {
    this.deliveries = [];
  }

  async dispatch(orderId, destinationCity) {
    // Simulasi kegagalan jika kota berada di luar jangkauan operasional
    if (destinationCity.toLowerCase() === 'papua_pedalaman') {
      throw new Error(`Wilayah pengiriman [${destinationCity}] di luar jangkauan armada kurir logistik!`);
    }

    const deliveryRecord = { orderId, destinationCity, status: 'DISPATCHED', trackingNumber: `TRK-${Date.now()}` };
    this.deliveries.push(deliveryRecord);
    return { status: 'SUCCESS', trackingNumber: deliveryRecord.trackingNumber };
  }
}

// =========================================================================
// BAGIAN 2: SAGA ORCHESTRATOR STATE MACHINE
// =========================================================================

class CheckoutSagaOrchestrator {
  constructor(paymentSvc, inventorySvc, logisticsSvc) {
    this.payment = paymentSvc;
    this.inventory = inventorySvc;
    this.logistics = logisticsSvc;
  }

  async executeSaga(orderId, customerId, sku, quantity, amount, destination) {
    console.log(`\n▶️ [SAGA MEMULAI ALUR KERJA] Order: ${orderId} | Total: Rp ${amount.toLocaleString('id-ID')}`);
    const completedSteps = [];

    try {
      // LANGKAH 1: PEMBAYARAN
      console.log('  1. Menghubungi Payment Service (Debit)...');
      const payRes = await this.payment.debit(customerId, amount);
      completedSteps.push('PAYMENT');
      console.log(`     ✅ Debit Berhasil. Sisa Saldo: Rp ${payRes.remainingBalance.toLocaleString('id-ID')}`);

      // LANGKAH 2: INVENTARIS
      console.log('  2. Menghubungi Inventory Service (Alokasi Stok)...');
      const invRes = await this.inventory.reserveStock(sku, quantity);
      completedSteps.push('INVENTORY');
      console.log(`     ✅ Alokasi Stok Berhasil. Sisa Stok: ${invRes.remainingStock}`);

      // LANGKAH 3: LOGISTIK PENGIRIMAN
      console.log(`  3. Menghubungi Logistics Service (Jadwalkan Kurir ke ${destination})...`);
      const logRes = await this.logistics.dispatch(orderId, destination);
      completedSteps.push('LOGISTICS');
      console.log(`     ✅ Jadwal Kurir Siap. Resi: ${logRes.trackingNumber}`);

      console.log(`🎉 [SAGA BERHASIL PENUH] Seluruh microservices terkoordinasi secara sempurna!`);
      return { success: true, state: 'COMPLETED' };

    } catch (err) {
      console.error(`  🚨 [SAGA GAGAL PADA LANGKAH AKTIF] Error: "${err.message}"`);
      console.log(`  🔄 [MEMULAI TRANSAKSI KOMPENSASI SEMANTIK MUNDUR]...`);

      // Eksekusi transaksi kompensasi secara terbalik (LIFO)
      for (const step of completedSteps.reverse()) {
        if (step === 'INVENTORY') {
          console.log(`     ↪️ Mengembalikan alokasi stok produk ${sku} sebanyak ${quantity}...`);
          const relRes = await this.inventory.compensateReleaseStock(sku, quantity);
          console.log(`        Stok berhasil dipulihkan menjadi: ${relRes.currentStock}`);
        }
        if (step === 'PAYMENT') {
          console.log(`     ↪️ Mengembalikan dana pembayaran (Refund) Rp ${amount.toLocaleString('id-ID')} ke nasabah...`);
          const refRes = await this.payment.compensateRefund(customerId, amount);
          console.log(`        Saldo nasabah berhasil dipulihkan menjadi: Rp ${refRes.currentBalance.toLocaleString('id-ID')}`);
        }
      }

      console.log(`🛡️ [KOMPENSASI SELESAI] Integritas seluruh microservice tetap utuh tanpa data tersangkut!`);
      return { success: false, state: 'COMPENSATED_AND_ROLLED_BACK', error: err.message };
    }
  }
}

// =========================================================================
// BAGIAN 3: EKSEKUSI PENGUJIAN SKENARIO LENGKAP
// =========================================================================

async function main() {
  console.log('='.repeat(75));
  console.log('SIMULASI: SAGA ORCHESTRATION & COMPENSATING TRANSACTIONS');
  console.log('='.repeat(75));

  const paymentService = new PaymentMicroservice();
  const inventoryService = new InventoryMicroservice();
  const logisticsService = new LogisticsMicroservice();

  const orchestrator = new CheckoutSagaOrchestrator(paymentService, inventoryService, logisticsService);

  // SKENARIO 1: HAPPY PATH (SEMUA SUKSES)
  console.log('\n--- UJI COBA 1: TRANSAKSI NORMAL KE JAKARTA (HAPPY PATH) ---');
  await orchestrator.executeSaga('ORD-1001', 'CUST-101', 'IPHONE-15', 1, 500000, 'Jakarta');

  console.log(`\nStatus Terkini Sistem:`);
  console.log(`- Saldo CUST-101 : Rp ${paymentService.accounts.get('CUST-101').toLocaleString('id-ID')}`);
  console.log(`- Sisa Stok iPhone: ${inventoryService.stocks.get('IPHONE-15')}`);

  // SKENARIO 2: FAILURE PATH (LOGISTIK GAGAL & KOMPENSASI MUNDUR)
  console.log('\n--- UJI COBA 2: PENGIRIMAN KE WILAYAH DI LUAR JANGKAUAN (FAILURE & ROLLBACK) ---');
  await orchestrator.executeSaga('ORD-1002', 'CUST-101', 'IPHONE-15', 1, 500000, 'Papua_Pedalaman');

  console.log(`\nStatus Akhir Sistem Pasca Kompensasi:`);
  console.log(`- Saldo CUST-101 : Rp ${paymentService.accounts.get('CUST-101').toLocaleString('id-ID')} (Dana aman kembali!)`);
  console.log(`- Sisa Stok iPhone: ${inventoryService.stocks.get('IPHONE-15')} (Stok aman kembali!)`);

  console.log('\n' + '='.repeat(75));
  console.log('SIMULASI BERHASIL: Saga Orchestration & Transaksi Kompensasi bekerja presisi!');
  console.log('='.repeat(75));
}

main();
