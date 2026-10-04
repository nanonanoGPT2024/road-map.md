/**
 * SIMULATOR: TACTICAL DOMAIN-DRIVEN DESIGN (DDD) AGGREGATE ROOT & DOMAIN EVENTS
 * Modul 01: Monolith, Modular Monolith, Microservices, & Domain-Driven Design (DDD)
 *
 * Mendemonstrasikan:
 * 1. Value Object Immutable: Money (dengan proteksi mutasi Object.freeze).
 * 2. Aggregate Root: OrderAggregate (menjaga batasan konsistensi & invariant bisnis).
 * 3. Domain Events Generation: Pengumpulan event bisnis saat state mutation.
 * 4. In-Memory Domain Event Dispatcher: Komunikasi antar Bounded Context yang terisolasi.
 *
 * Jalankan: node ddd_aggregate_root_sim.js
 */

// =========================================================================
// BAGIAN 1: VALUE OBJECT (IMMUTABLE BUSINESS ATOMS)
// =========================================================================

class Money {
  constructor(amount, currency = 'IDR') {
    if (typeof amount !== 'number' || isNaN(amount) || amount < 0) {
      throw new Error(`Nilai uang tidak valid: ${amount}`);
    }
    this.amount = Math.round(amount);
    this.currency = currency.toUpperCase();
    Object.freeze(this); // Menjamin immutability absolut!
  }

  add(other) {
    if (this.currency !== other.currency) {
      throw new Error(`Mata uang tidak cocok: ${this.currency} vs ${other.currency}`);
    }
    return new Money(this.amount + other.amount, this.currency);
  }

  multiply(multiplier) {
    if (multiplier < 0) throw new Error('Pengali tidak boleh negatif');
    return new Money(this.amount * multiplier, this.currency);
  }

  equals(other) {
    return other instanceof Money &&
      this.amount === other.amount &&
      this.currency === other.currency;
  }

  format() {
    return `${this.currency} ${this.amount.toLocaleString('id-ID')}`;
  }
}

// =========================================================================
// BAGIAN 2: AGGREGATE ROOT & ENTITIES (CONSISTENCY BOUNDARY)
// =========================================================================

class OrderItem {
  constructor(sku, productName, unitPriceMoney, quantity) {
    this.sku = sku;
    this.productName = productName;
    this.unitPrice = unitPriceMoney; // Value Object
    this.quantity = quantity;
  }

  getSubtotal() {
    return this.unitPrice.multiply(this.quantity);
  }
}

class OrderAggregateRoot {
  constructor(orderId, customerId) {
    this.id = orderId;
    this.customerId = customerId;
    this.items = []; // Dilindungi oleh Aggregate Root
    this.status = 'DRAFT';
    this.domainEvents = []; // Event yang akan dipublikasikan
  }

  // Aturan Bisnis 1: Modifikasi item hanya boleh saat status DRAFT
  addItem(sku, productName, unitPriceMoney, quantity) {
    if (this.status !== 'DRAFT') {
      throw new Error(`Tidak diizinkan mengubah item: Pesanan sudah berstatus [${this.status}]`);
    }
    if (quantity <= 0) {
      throw new Error('Kuantitas item minimal 1');
    }

    const existingIndex = this.items.findIndex(i => i.sku === sku);
    if (existingIndex >= 0) {
      this.items[existingIndex].quantity += quantity;
    } else {
      this.items.push(new OrderItem(sku, productName, unitPriceMoney, quantity));
    }
  }

  // Aturan Bisnis 2: Checkout hanya sah jika keranjang memiliki item
  checkout() {
    if (this.items.length === 0) {
      throw new Error('Gagal Checkout: Pesanan tidak memiliki item!');
    }
    if (this.status !== 'DRAFT') {
      throw new Error(`Pesanan sudah berstatus [${this.status}], tidak dapat checkout ulang.`);
    }

    this.status = 'CONFIRMED';
    const total = this.calculateTotal();

    // Merekam Domain Event
    this.recordDomainEvent({
      eventType: 'ORDER_CONFIRMED_EVENT',
      orderId: this.id,
      customerId: this.customerId,
      totalAmount: total.amount,
      currency: total.currency,
      itemCount: this.items.length,
      occurredAt: new Date().toISOString()
    });
  }

  // Aturan Bisnis 3: Pembatalan hanya boleh jika belum dikirim
  cancel(reason) {
    if (this.status === 'SHIPPED' || this.status === 'DELIVERED') {
      throw new Error('Pesanan yang sudah dalam pengiriman tidak dapat dibatalkan!');
    }
    if (this.status === 'CANCELLED') {
      throw new Error('Pesanan sudah dalam kondisi dibatalkan.');
    }

    this.status = 'CANCELLED';

    this.recordDomainEvent({
      eventType: 'ORDER_CANCELLED_EVENT',
      orderId: this.id,
      customerId: this.customerId,
      reason,
      occurredAt: new Date().toISOString()
    });
  }

  calculateTotal() {
    let total = new Money(0, 'IDR');
    for (const item of this.items) {
      total = total.add(item.getSubtotal());
    }
    return total;
  }

  recordDomainEvent(event) {
    this.domainEvents.push(event);
  }

  pullDomainEvents() {
    const events = [...this.domainEvents];
    this.domainEvents = []; // Kosongkan setelah dipull
    return events;
  }
}

// =========================================================================
// BAGIAN 3: DOMAIN EVENT BUS (KOMUNIKASI LINTAS BOUNDED CONTEXT)
// =========================================================================

class DomainEventBus {
  constructor() {
    this.handlers = new Map();
  }

  subscribe(eventType, handler) {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, []);
    }
    this.handlers.get(eventType).push(handler);
  }

  publish(events) {
    for (const event of events) {
      const listeners = this.handlers.get(event.eventType) || [];
      for (const listener of listeners) {
        listener(event);
      }
    }
  }
}

// =========================================================================
// BAGIAN 4: EKSEKUSI PENGUJIAN SKENARIO LENGKAP
// =========================================================================

function main() {
  console.log('='.repeat(75));
  console.log('SIMULASI: DOMAIN-DRIVEN DESIGN (DDD) AGGREGATE ROOT & DOMAIN EVENTS');
  console.log('='.repeat(75));

  const eventBus = new DomainEventBus();

  // Mendaftarkan Bounded Context lain sebagai pendengar event:
  eventBus.subscribe('ORDER_CONFIRMED_EVENT', (evt) => {
    console.log(`  📦 [Warehouse Bounded Context] Mengalokasikan stok barang di gudang untuk Order: ${evt.orderId}`);
  });
  eventBus.subscribe('ORDER_CONFIRMED_EVENT', (evt) => {
    console.log(`  📧 [Notification Context] Mengirim email konfirmasi tagihan ${evt.currency} ${evt.totalAmount.toLocaleString('id-ID')} ke Nasabah ${evt.customerId}`);
  });
  eventBus.subscribe('ORDER_CANCELLED_EVENT', (evt) => {
    console.log(`  🔄 [Inventory Context] Mengembalikan alokasi inventaris barang karena Order ${evt.orderId} DIBATALKAN. Alasan: "${evt.reason}"`);
  });

  // 1. Membangun Aggregate Root
  console.log('\n1. Membuat Pesanan Baru (Aggregate Root: Order)...');
  const order = new OrderAggregateRoot('ORD-99881', 'CUST-ALPHA');

  // 2. Menambahkan Item (Value Object Money)
  console.log('2. Menambahkan Produk ke dalam Keranjang...');
  order.addItem('LAPTOP-01', 'MacBook Pro M3 Max 16"', new Money(42000000, 'IDR'), 1);
  order.addItem('MOUSE-02',  'Magic Mouse Space Black', new Money(1450000, 'IDR'), 2);

  console.log(`   Total Sementara: ${order.calculateTotal().format()}`);
  console.log(`   Status Pesanan  : ${order.status}`);

  // 3. Eksekusi Checkout
  console.log('\n3. Menjalankan Perintah order.checkout()...');
  order.checkout();
  console.log(`   Status Akhir    : ${order.status}`);

  // 4. Publikasikan Domain Events
  console.log('\n4. Mempublikasikan Domain Events ke Event Bus:');
  const events = order.pullDomainEvents();
  console.log(`   Ditemukan ${events.length} Domain Event yang diterbitkan oleh Aggregate Root.`);
  eventBus.publish(events);

  // 5. Uji Coba Pelanggaran Invariant Bisnis
  console.log('\n5. Uji Kasus: Mencoba Memodifikasi Item Pada Pesanan Yang Sudah CONFIRMED:');
  try {
    order.addItem('CABLE-01', 'USB-C Cable', new Money(250000, 'IDR'), 1);
  } catch (err) {
    console.log(`   🛡️ [INVARIANT DITEGAKKAN] Aggregate Root menolak modifikasi: "${err.message}"`);
  }

  // 6. Uji Pembatalan Pesanan
  console.log('\n6. Menjalankan Perintah order.cancel()...');
  order.cancel('Nasabah ingin mengubah metode pembayaran');
  console.log(`   Status Pesanan  : ${order.status}`);
  const cancelEvents = order.pullDomainEvents();
  eventBus.publish(cancelEvents);

  console.log('\n' + '='.repeat(75));
  console.log('SIMULASI BERHASIL: Seluruh pilar taktis DDD bekerja dengan integritas penuh!');
  console.log('='.repeat(75));
}

main();
