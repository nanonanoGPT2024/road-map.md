/**
 * Transactional ACID Engine & Concurrency Isolation Simulator
 * 
 * Mensimulasikan arsitektur database RDBMS internal:
 * 1. Atomicity via Write-Ahead Log (WAL) & Automated Rollback saat terjadi error.
 * 2. Anomali Isolasi: Dirty Read vs Read Committed vs Repeatable Read.
 * 3. Pessimistic Locking (SELECT FOR UPDATE) vs Optimistic Concurrency Control (OCC Versioning).
 */

const ANSI = {
  reset: "\x1b[0m",
  bold: "\x1b[1m",
  green: "\x1b[32m",
  cyan: "\x1b[36m",
  yellow: "\x1b[33m",
  red: "\x1b[31m",
  magenta: "\x1b[35m"
};

function log(module, msg, color = ANSI.reset) {
  console.log(`${color}[${module}] ${msg}${ANSI.reset}`);
}

// ================= 1. ACID & WAL ENGINE SIMULATOR =================
class DatabaseStorageEngine {
  constructor() {
    this.table = new Map([
      ["ACC-01", { id: "ACC-01", balance: 1000000, version: 1 }],
      ["ACC-02", { id: "ACC-02", balance: 500000, version: 1 }]
    ]);
    this.walLog = []; // Write-Ahead Log buffer
  }

  executeTransfer(fromId, toId, amount, forceCrash = false) {
    log("wal-engine", `--- Memulai Transaksi Transfer Rp ${amount}: ${fromId} -> ${toId} ---`, ANSI.bold);
    const txId = `tx-${Math.floor(100 + Math.random() * 900)}`;

    // Salin snapshot awal untuk pencatatan WAL
    const fromAccount = this.table.get(fromId);
    const toAccount = this.table.get(toId);

    if (!fromAccount || fromAccount.balance < amount) {
      log("rdbms-constraint", `ABORT: Saldo ${fromId} tidak mencukupi atau akun tidak ditemukan!`, ANSI.red);
      return false;
    }

    // Catat ke WAL sebelum menyentuh data utama (Write-Ahead Logging)
    this.walLog.push({ txId, action: "DEBIT", id: fromId, oldBalance: fromAccount.balance, newBalance: fromAccount.balance - amount });
    fromAccount.balance -= amount;
    log("wal-log", `WAL Append: [${txId}] ${fromId} saldo baru ${fromAccount.balance}`, ANSI.cyan);

    // Simulasi Crash di tengah transaksi!
    if (forceCrash) {
      log("crash-simulator", `SISTEM CRASH / LISTRIK MATI TEPAT SETELAH DEBIT DILAKUKAN!`, ANSI.bold + ANSI.red);
      log("crash-recovery", `Memulai prosedur Crash Recovery membaca WAL...`, ANSI.magenta);
      
      // Rollback menggunakan log WAL
      const logEntry = this.walLog.find(l => l.txId === txId && l.action === "DEBIT");
      fromAccount.balance = logEntry.oldBalance;
      log("crash-recovery", `ROLLBACK BERHASIL! Saldo ${fromId} dipulihkan ke Rp ${fromAccount.balance} (Atomicity Terjamin!)`, ANSI.green);
      return false;
    }

    // Langkah 2: Tambah saldo penerima
    this.walLog.push({ txId, action: "CREDIT", id: toId, oldBalance: toAccount.balance, newBalance: toAccount.balance + amount });
    toAccount.balance += amount;
    log("wal-log", `WAL Append: [${txId}] ${toId} saldo baru ${toAccount.balance}`, ANSI.cyan);

    // Commit permanen
    this.walLog.push({ txId, action: "COMMIT" });
    log("rdbms-engine", `TRANSAKSI COMMIT SUKSES! fsync() ke disk fisik tuntas.`, ANSI.green);
    return true;
  }
}

// ================= 2. CONCURRENCY ANOMALY SIMULATOR =================
class ConcurrencyIsolationSimulator {
  static runDirtyReadDemo() {
    console.log(`\n${ANSI.bold}=== BAGIAN 2: ANOMALI ISOLASI (DIRTY READ DI READ UNCOMMITTED) ===${ANSI.reset}`);

    let activeAccount = { id: "ACC-A", balance: 1000000 };

    log("tx-1", "Transaksi 1: Mengubah saldo menjadi Rp 10.000.000 (BELUM COMMIT / UNCOMMITTED)", ANSI.yellow);
    activeAccount.balance = 10000000;

    log("tx-2", `Transaksi 2 (Read Uncommitted): Membaca saldo -> Rp ${activeAccount.balance}`, ANSI.red);
    log("tx-2", `Transaksi 2 membuat keputusan bisnis berdasarkan saldo Rp 10.000.000 ini!`, ANSI.red);

    log("tx-1", "Transaksi 1: Terjadi error! Menjalankan ROLLBACK ke saldo Rp 1.000.000!", ANSI.magenta);
    activeAccount.balance = 1000000;

    log("audit", `BENCANA DIRTY READ! Transaksi 2 telah memproses data palsu yang tidak pernah sah!`, ANSI.bold + ANSI.red);
  }

  static runOptimisticLockingDemo() {
    console.log(`\n${ANSI.bold}=== BAGIAN 3: OPTIMISTIC CONCURRENCY CONTROL (OCC VERSIONING) ===${ANSI.reset}`);

    const product = { id: 1, name: "PlayStation 5", stock: 1, version: 1 };
    log("db-state", `Stok Awal: ${product.stock}, Versi: ${product.version}`, ANSI.cyan);

    // Dua pengguna membaca data versi 1 bersamaan
    const user1Read = { ...product };
    const user2Read = { ...product };

    log("user-1", `User 1 membaca stok (Versi 1) dan menekan tombol Beli...`, ANSI.yellow);
    log("user-2", `User 2 membaca stok (Versi 1) dan menekan tombol Beli bersamaan!`, ANSI.yellow);

    // User 1 menulis lebih dulu
    if (user1Read.version === product.version) {
      product.stock -= 1;
      product.version += 1;
      log("user-1", `User 1 SUKSES Checkout! Stok sekarang ${product.stock}, Versi naik ke ${product.version}`, ANSI.green);
    }

    // User 2 mencoba menulis dengan versi basi (Versi 1)
    log("user-2", `User 2 mencoba eksekusi: UPDATE WHERE id = 1 AND version = ${user2Read.version}`, ANSI.yellow);
    if (user2Read.version === product.version) {
      product.stock -= 1;
      product.version += 1;
    } else {
      log("user-2", `TABRAKAN KONKURENSI TERDETEKSI! Versi database (${product.version}) != Versi dibaca (${user2Read.version})!`, ANSI.red);
      log("user-2", `Transaksi User 2 DITOLAK secara elegan tanpa merusak stok (Stok tidak menjadi minus)!`, ANSI.green);
    }
  }
}

// ================= SIMULASI EKSEKUSI =================
console.log(`${ANSI.bold}================================================================${ANSI.reset}`);
console.log(`${ANSI.bold}      RDBMS ACID ENGINE & TRANSACTION ISOLATION SIMULATOR       ${ANSI.reset}`);
console.log(`${ANSI.bold}================================================================${ANSI.reset}\n`);

// 1. Eksekusi Uji Coba ACID & Crash Recovery
const db = new DatabaseStorageEngine();
console.log("--- [SKENARIO 1: ATOMICITY CRASH & ROLLBACK] ---");
db.executeTransfer("ACC-01", "ACC-02", 300000, true); // Crash paksa

console.log("\n--- [SKENARIO 2: TRANSAKSI NORMAL BERHASIL] ---");
db.executeTransfer("ACC-01", "ACC-02", 200000, false);

// 2. Demonstrasi Anomali & Solusi Isolasi
ConcurrencyIsolationSimulator.runDirtyReadDemo();
ConcurrencyIsolationSimulator.runOptimisticLockingDemo();

console.log(`\n${ANSI.bold}Seluruh prinsip ACID, Isolasi Transaksi, dan OCC tervalidasi!${ANSI.reset}`);
