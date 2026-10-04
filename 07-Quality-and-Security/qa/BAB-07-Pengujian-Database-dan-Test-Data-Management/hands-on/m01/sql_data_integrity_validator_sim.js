/**
 * Hands-on M01: SQL Data Integrity Validator, ACID Transaction & Migration Simulator
 * 
 * Demonstrasi:
 * 1. Virtual Relational Database Engine (PK, FK, CHECK Constraints, NOT NULL).
 * 2. ACID Transaction Manager dengan Failure Injection & Rollback otomatis.
 * 3. Auditor Integritas Relasional (Mendeteksi Foreign Key violations & Orphaned records).
 * 4. Simulator Migrasi Skema (Up migration + Down rollback verification).
 */

const ANSI = {
  reset: "\x1b[0m",
  green: "\x1b[32m",
  red: "\x1b[31m",
  yellow: "\x1b[33m",
  cyan: "\x1b[36m",
  bold: "\x1b[1m",
  dim: "\x1b[2m"
};

// ==========================================
// 1. VIRTUAL RELATIONAL DATABASE ENGINE
// ==========================================
class VirtualDatabase {
  constructor() {
    this.tables = {
      accounts: new Map(), // id -> { id, name, balance }
      transfers: new Map() // id -> { id, from_id, to_id, amount }
    };
    this.inTransaction = false;
    this.snapshot = null;
  }

  // ACID: Begin Transaction
  beginTransaction() {
    if (this.inTransaction) throw new Error("Transaksi sudah aktif!");
    this.inTransaction = true;
    // Buat deep snapshot memori untuk rollback
    this.snapshot = {
      accounts: new Map(JSON.parse(JSON.stringify(Array.from(this.tables.accounts.entries())))),
      transfers: new Map(JSON.parse(JSON.stringify(Array.from(this.tables.transfers.entries()))))
    };
  }

  // ACID: Commit Transaction
  commit() {
    if (!this.inTransaction) throw new Error("Tidak ada transaksi aktif untuk di-commit!");
    this.inTransaction = false;
    this.snapshot = null;
  }

  // ACID: Rollback Transaction
  rollback() {
    if (!this.inTransaction) throw new Error("Tidak ada transaksi aktif untuk di-rollback!");
    this.tables.accounts = this.snapshot.accounts;
    this.tables.transfers = this.snapshot.transfers;
    this.inTransaction = false;
    this.snapshot = null;
  }

  // Table Operations with Constraints Enforcement
  insertAccount({ id, name, balance }) {
    if (!id || !name) throw new Error("CONSTRAINT ERROR: id dan name wajib diisi (NOT NULL)");
    if (this.tables.accounts.has(id)) throw new Error(`PRIMARY KEY VIOLATION: Account ${id} sudah terdaftar`);
    if (typeof balance !== "number" || balance < 0) {
      throw new Error(`CHECK CONSTRAINT VIOLATION: Saldo tidak boleh bernilai negatif (balance >= 0)`);
    }
    this.tables.accounts.set(id, { id, name, balance });
  }

  updateBalance(accountId, delta) {
    const acc = this.tables.accounts.get(accountId);
    if (!acc) throw new Error(`ACCOUNT NOT FOUND: ${accountId}`);
    const newBalance = acc.balance + delta;
    if (newBalance < 0) {
      throw new Error(`CHECK CONSTRAINT VIOLATION: Saldo ${accountId} tidak mencukupi (hasil: ${newBalance} < 0)`);
    }
    acc.balance = newBalance;
  }

  insertTransfer({ id, from_id, to_id, amount }) {
    // Referential Integrity (Foreign Key Checks)
    if (!this.tables.accounts.has(from_id)) {
      throw new Error(`FOREIGN KEY VIOLATION: Pengirim [${from_id}] tidak ditemukan di tabel accounts!`);
    }
    if (!this.tables.accounts.has(to_id)) {
      throw new Error(`FOREIGN KEY VIOLATION: Penerima [${to_id}] tidak ditemukan di tabel accounts!`);
    }
    if (amount <= 0) throw new Error(`CHECK CONSTRAINT VIOLATION: Nominal transfer harus > 0`);

    this.tables.transfers.set(id, { id, from_id, to_id, amount });
  }

  deleteAccount(accountId) {
    // Foreign Key ON DELETE RESTRICT Check
    for (const tx of this.tables.transfers.values()) {
      if (tx.from_id === accountId || tx.to_id === accountId) {
        throw new Error(
          `RESTRICT DELETE VIOLATION: Akun [${accountId}] tidak dapat dihapus karena masih memiliki relasi transaksi aktif!`
        );
      }
    }
    this.tables.accounts.delete(accountId);
  }
}

// ==========================================
// 2. MAIN SIMULATION EXECUTION
// ==========================================
function main() {
  console.log(`${ANSI.bold}╔═══════════════════════════════════════════════════════════════╗`);
  console.log(`║      DATABASE TESTING: INTEGRITY, ACID & MIGRATION LAB        ║`);
  console.log(`╚═══════════════════════════════════════════════════════════════╝${ANSI.reset}`);

  const db = new VirtualDatabase();

  // Setup Initial Data
  db.insertAccount({ id: "ACC-01", name: "Budi Santoso", balance: 500000 });
  db.insertAccount({ id: "ACC-02", name: "Dewi Lestari", balance: 100000 });

  // 1. UJI INTEGRITAS KONSTRAIN DASAR
  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 1. UJI KONSTRAIN SKEMA (CHECK & PRIMARY KEY) ===${ANSI.reset}`);
  
  // Test A: Penolakan Saldo Negatif (CHECK)
  try {
    db.insertAccount({ id: "ACC-03", name: "Hacker Minus", balance: -50000 });
  } catch (err) {
    console.log(`  ${ANSI.green}✓ PASS${ANSI.reset} Database menolak saldo awal negatif: "${err.message}"`);
  }

  // Test B: Penolakan Duplikasi Primary Key
  try {
    db.insertAccount({ id: "ACC-01", name: "Duplikat Budi", balance: 20000 });
  } catch (err) {
    console.log(`  ${ANSI.green}✓ PASS${ANSI.reset} Database menolak duplikasi Primary Key: "${err.message}"`);
  }

  // 2. UJI INTEGRITAS REFERENSIAL (FOREIGN KEY & ORPHAN PREVENTION)
  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 2. UJI INTEGRITAS REFERENSIAL (FOREIGN KEY RESTRICTIONS) ===${ANSI.reset}`);
  
  // Test C: Foreign Key Violation (Akun Fiktif)
  try {
    db.insertTransfer({ id: "TX-101", from_id: "ACC-01", to_id: "ACC_FIKTIF_99", amount: 50000 });
  } catch (err) {
    console.log(`  ${ANSI.green}✓ PASS${ANSI.reset} Foreign Key mencegah transfer ke akun tidak dikenal: "${err.message}"`);
  }

  // Buat transaksi sah
  db.insertTransfer({ id: "TX-102", from_id: "ACC-01", to_id: "ACC-02", amount: 50000 });
  console.log(`  Transaksi TX-102 sah berhasil dicatat antara ACC-01 dan ACC-02.`);

  // Test D: Restrict Delete
  try {
    db.deleteAccount("ACC-01");
  } catch (err) {
    console.log(`  ${ANSI.green}✓ PASS${ANSI.reset} ON DELETE RESTRICT melindungi akun berelasi aktif: "${err.message}"`);
  }

  // 3. UJI TRANSAKSI ACID & ATOMICITY FAILURE ROLLBACK
  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 3. UJI TRANSAKSI ACID (FAILURE INJECTION & ROLLBACK) ===${ANSI.reset}`);
  console.log(`  Kondisi Awal: ACC-01 Saldo = ${db.tables.accounts.get("ACC-01").balance.toLocaleString("id-ID")}`);

  db.beginTransaction();
  try {
    console.log("  [Step 1] Memotong saldo ACC-01 sebesar Rp 200.000...");
    db.updateBalance("ACC-01", -200000);

    console.log("  [Step 2] Sengaja memicu error: Injeksi transfer ke akun fiktif...");
    db.insertTransfer({ id: "TX-ERROR", from_id: "ACC-01", to_id: "ACC_HILANG", amount: 200000 });

    db.commit(); // Tidak akan tercapai
  } catch (err) {
    console.log(`  ${ANSI.yellow}→ Injeksi Error Terdeteksi: ${err.message}${ANSI.reset}`);
    console.log(`  [Step 3] Mengeksekusi ROLLBACK pembatalan darurat...`);
    db.rollback();
  }

  const postBalance = db.tables.accounts.get("ACC-01").balance;
  console.log(`  Kondisi Akhir: ACC-01 Saldo = ${postBalance.toLocaleString("id-ID")}`);

  if (postBalance === 500000) {
    console.log(`  ${ANSI.green}✓ PASS (ACID ATOMICITY)${ANSI.reset} Saldo pengirim 100% utuh, tidak ada uang bocor!`);
  } else {
    console.log(`  ${ANSI.red}✗ FAIL: Saldo bocor setelah rollback!${ANSI.reset}`);
  }

  // 4. UJI MIGRASI SKEMA DATABASE (UP & DOWN ROLLBACK)
  console.log(`\n${ANSI.bold}${ANSI.cyan}=== 4. UJI MIGRASI SKEMA (SCHEMA EVOLUTION) ===${ANSI.reset}`);
  console.log("  [Up Migration: V2] Menambahkan kolom 'loyalty_points' default 0 ke tabel accounts...");
  for (const acc of db.tables.accounts.values()) {
    acc.loyalty_points = 0; // Migrasi UP
  }
  console.log(`    ${ANSI.green}✓ UP Migration Berhasil:${ANSI.reset} Semua akun memiliki kolom 'loyalty_points': ${db.tables.accounts.get("ACC-01").loyalty_points}`);

  console.log("  [Down Migration: V1] Rollback pembatalan darurat kolom 'loyalty_points'...");
  for (const acc of db.tables.accounts.values()) {
    delete acc.loyalty_points; // Migrasi DOWN
  }
  console.log(`    ${ANSI.green}✓ DOWN Migration Berhasil:${ANSI.reset} Kolom dibatalkan, data historis tetap aman.`);

  console.log(`\n${ANSI.green}✓ SQL Data Integrity & ACID Lab executed successfully!${ANSI.reset}\n`);
}

main();
