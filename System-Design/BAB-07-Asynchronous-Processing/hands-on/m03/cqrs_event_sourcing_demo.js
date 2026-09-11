/**
 * LAB SIMULATION: Event Sourcing, Snapshotting, & CQRS Read Projection
 * 
 * Tujuan:
 * 1. Menunjukkan Aggregate yang tidak memiliki kolom saldo di database, saldo dihitung dari event.
 * 2. Menunjukkan fitur Snapshot untuk mempercepat rehidrasi state ribuan event.
 * 3. Menunjukkan Temporal Query (melihat saldo di masa lalu).
 * 4. Menunjukkan CQRS Projection yang memperbarui Read-Optimized View secara asinkron.
 */

// 1. EVENT STORE (WRITE MODEL)
class InMemoryEventStore {
  constructor() {
    this.streams = new Map(); // streamId -> Array of Events
  }

  append(streamId, event) {
    if (!this.streams.has(streamId)) {
      this.streams.set(streamId, []);
    }
    const events = this.streams.get(streamId);
    const version = events.length + 1;
    const enrichedEvent = { ...event, version, timestamp: Date.now() };
    events.push(enrichedEvent);
    return enrichedEvent;
  }

  getEvents(streamId, fromVersion = 0) {
    const events = this.streams.get(streamId) || [];
    return events.filter(e => e.version > fromVersion);
  }
}

// 2. DOMAIN AGGREGATE (BANK ACCOUNT)
class BankAccountAggregate {
  constructor(accountId) {
    this.accountId = accountId;
    this.balance = 0;
    this.owner = null;
    this.version = 0;
  }

  // Pure function: state transition berdasarkan event
  apply(event) {
    switch (event.type) {
      case "AccountOpened":
        this.owner = event.payload.owner;
        this.balance = event.payload.initialDeposit;
        break;
      case "MoneyDeposited":
        this.balance += event.payload.amount;
        break;
      case "MoneyWithdrawn":
        this.balance -= event.payload.amount;
        break;
    }
    this.version = event.version;
  }

  // Rehydrate state dari event stream (atau dari snapshot)
  static rehydrate(accountId, events, snapshot = null) {
    const account = new BankAccountAggregate(accountId);
    if (snapshot) {
      account.owner = snapshot.owner;
      account.balance = snapshot.balance;
      account.version = snapshot.version;
    }
    for (const event of events) {
      account.apply(event);
    }
    return account;
  }
}

// 3. CQRS READ MODEL (DENORMALIZED VIEW)
class AccountSummaryReadModel {
  constructor() {
    this.view = new Map(); // accountId -> Read-optimized summary DTO
  }

  project(event) {
    const id = event.streamId;
    if (event.type === "AccountOpened") {
      this.view.set(id, {
        accountId: id,
        owner: event.payload.owner,
        currentBalance: event.payload.initialDeposit,
        totalTransactions: 1,
        lastUpdated: event.timestamp
      });
    } else {
      const current = this.view.get(id);
      if (current) {
        if (event.type === "MoneyDeposited") current.currentBalance += event.payload.amount;
        if (event.type === "MoneyWithdrawn") current.currentBalance -= event.payload.amount;
        current.totalTransactions += 1;
        current.lastUpdated = event.timestamp;
      }
    }
  }

  query(accountId) {
    return this.view.get(accountId);
  }
}

// ======================= EKSEKUSI PENGUJIAN =======================
const eventStore = new InMemoryEventStore();
const readModel = new AccountSummaryReadModel();
const accountId = "ACC-ID-999";

console.log("===================================================================");
console.log("🛠️  LANGKAH 1: MENULIS DOMAIN EVENTS KE EVENT STORE");
console.log("===================================================================\n");

const e1 = eventStore.append(accountId, { streamId: accountId, type: "AccountOpened", payload: { owner: "Budi Santoso", initialDeposit: 500000 } });
readModel.project(e1);
console.log(`[Event Store] Appended v${e1.version}: AccountOpened (Rp 500.000)`);

const e2 = eventStore.append(accountId, { streamId: accountId, type: "MoneyDeposited", payload: { amount: 200000 } });
readModel.project(e2);
console.log(`[Event Store] Appended v${e2.version}: MoneyDeposited (+ Rp 200.000)`);

const e3 = eventStore.append(accountId, { streamId: accountId, type: "MoneyWithdrawn", payload: { amount: 150000 } });
readModel.project(e3);
console.log(`[Event Store] Appended v${e3.version}: MoneyWithdrawn (- Rp 150.000)`);

console.log("\n===================================================================");
console.log("🛠️  LANGKAH 2: REKONSTRUKSI STATE DARI RIWAYAT EVENT");
console.log("===================================================================\n");

const allEvents = eventStore.getEvents(accountId);
const reconstructed = BankAccountAggregate.rehydrate(accountId, allEvents);
console.log(`Rekonstruksi Akun: Pemilik = "${reconstructed.owner}", Saldo Terkini = Rp ${reconstructed.balance.toLocaleString('id-ID')} (Versi: ${reconstructed.version})`);

console.log("\n===================================================================");
console.log("🛠️  LANGKAH 3: TEMPORAL QUERY (TIME TRAVEL KE VERSI 2)");
console.log("===================================================================\n");
const pastEvents = eventStore.getEvents(accountId).filter(e => e.version <= 2);
const pastState = BankAccountAggregate.rehydrate(accountId, pastEvents);
console.log(`Audit Saldo pada Versi 2 (Sebelum Penarikan): Rp ${pastState.balance.toLocaleString('id-ID')}`);

console.log("\n===================================================================");
console.log("🛠️  LANGKAH 4: SNAPSHOTTING UNTUK OPTIMASI PERFORMA");
console.log("===================================================================\n");
// Buat snapshot di versi 3
const snapshotAtV3 = {
  owner: reconstructed.owner,
  balance: reconstructed.balance,
  version: reconstructed.version
};
console.log(`📸 Snapshot dibuat pada Versi 3: Saldo = Rp ${snapshotAtV3.balance.toLocaleString('id-ID')}`);

// Tambahkan transaksi baru di versi 4
const e4 = eventStore.append(accountId, { streamId: accountId, type: "MoneyDeposited", payload: { amount: 300000 } });
readModel.project(e4);
console.log(`[Event Store] Appended v${e4.version}: MoneyDeposited (+ Rp 300.000)`);

// Rehydrate HANYA dari snapshot + event baru (efisiensi O(1) + delta)
const deltaEvents = eventStore.getEvents(accountId, snapshotAtV3.version);
const fastReconstructed = BankAccountAggregate.rehydrate(accountId, deltaEvents, snapshotAtV3);
console.log(`Rehidrasi Cepat (Snapshot + 1 Event Delta): Saldo Akhir = Rp ${fastReconstructed.balance.toLocaleString('id-ID')}`);

console.log("\n===================================================================");
console.log("🛠️  LANGKAH 5: QUERY CQRS READ MODEL");
console.log("===================================================================\n");
console.log("Hasil query Read Model (Denormalized Materialized View):");
console.log(JSON.stringify(readModel.query(accountId), null, 2));

console.log("\n Kesimpulan:");
console.log("1. State saat ini adalah jumlah dari seluruh event historis.");
console.log("2. Audit trail dan Time-travel terwujud secara alami tanpa tabel log terpisah.");
console.log("3. Read Model dapat di-scale dan disajikan dalam bentuk denormalized view siap baca.");
