// replication_lag_sim.js
// Simulator Database Replication Lag & Mitigasi Session Consistency (Read-After-Write)

class DatabaseCluster {
  constructor(replicationLagMs = 250) {
    this.lagMs = replicationLagMs;

    // State data di Primary Node
    this.primaryStore = new Map([
      ["user:101", { id: "user:101", name: "Budi Santoso", status: "Active" }]
    ]);

    // State data di Read Replica Node (Awalnya sinkron)
    this.replicaStore = new Map([
      ["user:101", { id: "user:101", name: "Budi Santoso", status: "Active" }]
    ]);
  }

  // Operasi Tulis (Hanya diterima oleh Primary DB)
  async writePrimary(key, value) {
    this.primaryStore.set(key, { ...value });
    console.log(`\n  📝 [PRIMARY DB]: Menulis data baru untuk "${key}" -> Name: "${value.name}" (Sukses di Primary)`);

    // Replikasi ke Replica di-trigger secara asinkron dengan jeda waktu (Lag)
    setTimeout(() => {
      this.replicaStore.set(key, { ...value });
      console.log(`  🔄 [REPLICA DB]: Menerima & menerapkan pembaruan untuk "${key}" (Replikasi Selesai setelah ${this.lagMs}ms).`);
    }, this.lagMs);

    return true;
  }

  // Operasi Baca dari Replica
  async readReplica(key) {
    return this.replicaStore.has(key) ? { ...this.replicaStore.get(key) } : null;
  }

  // Operasi Baca langsung dari Primary
  async readPrimary(key) {
    return this.primaryStore.has(key) ? { ...this.primaryStore.get(key) } : null;
  }
}

// Router Pintar dengan Dukungan Session Consistency
class SmartDatabaseRouter {
  constructor(dbCluster) {
    this.db = dbCluster;
    this.userLastWriteTimestamps = new Map(); // userId -> timestamp
  }

  async updateUserProfile(userId, newProfile) {
    await this.db.writePrimary(userId, newProfile);
    // Catat waktu penulisan terakhir oleh pengguna ini
    this.userLastWriteTimestamps.set(userId, Date.now());
  }

  // Pola Naif (Selalu Baca dari Replica) - Rentan Stale Read!
  async getUserNaive(userId) {
    const data = await this.db.readReplica(userId);
    return { data, source: "Read Replica (Naif)" };
  }

  // Pola Cerdas (Session Consistency):
  // Jika user baru saja menulis dalam 400ms terakhir -> Paksa baca dari Primary!
  async getUserWithSessionConsistency(userId) {
    const lastWrite = this.userLastWriteTimestamps.get(userId) || 0;
    const timeSinceLastWrite = Date.now() - lastWrite;

    if (timeSinceLastWrite < 400) {
      const data = await this.db.readPrimary(userId);
      return { data, source: `Primary DB (Session Consistency Protection: Write terjadi ${timeSinceLastWrite}ms lalu)` };
    }

    const data = await this.db.readReplica(userId);
    return { data, source: "Read Replica (Aman: Tidak ada recent write)" };
  }
}

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function runDemo() {
  console.log("===================================================================");
  console.log("   SIMULATOR DATABASE REPLICATION LAG & SESSION CONSISTENCY        ");
  console.log("===================================================================");
  console.log(" - Primary Database & Read Replica aktif.");
  console.log(" - Simulasi Asynchronous Replication Lag: 250 ms.\n");

  const cluster = new DatabaseCluster(250);
  const router = new SmartDatabaseRouter(cluster);

  const userId = "user:101";

  // SKENARIO 1: Pengguna Mengupdate Profilnya
  console.log(">>> [LANGKAH 1]: Budi mengupdate namanya menjadi 'Budi Santoso, S.Kom'");
  await router.updateUserProfile(userId, { id: userId, name: "Budi Santoso, S.Kom", status: "Active" });

  // SKENARIO 2: Pembacaan Naif Tepat 50ms setelah penulisan (Terkena Replication Lag!)
  await sleep(50);
  console.log("\n>>> [LANGKAH 2]: Aplikasi me-refresh halaman 50ms kemudian menggunakan Router Naif:");
  const naiveRes = await router.getUserNaive(userId);
  console.log(` - Hasil Baca: Nama = "${naiveRes.data.name}"`);
  console.log(` - Sumber    : ${naiveRes.source}`);
  console.log(` ❌ ANOMALI STALE READ TERJADI! Nama baru hilang karena Replica belum selesai sinkron.`);

  // SKENARIO 3: Pembacaan dengan Session Consistency Router
  console.log("\n>>> [LANGKAH 3]: Aplikasi me-refresh halaman menggunakan Router Session Consistency:");
  const smartRes = await router.getUserWithSessionConsistency(userId);
  console.log(` - Hasil Baca: Nama = "${smartRes.data.name}"`);
  console.log(` - Sumber    : ${smartRes.source}`);
  console.log(` ✅ SUKSES! Data teranyar berhasil ditampilkan tanpa menunggu replica selesai lag.`);

  // SKENARIO 4: Menunggu 350ms hingga Replikasi Benar-Benar Selesai
  console.log("\n>>> [LANGKAH 4]: Menunggu 350ms hingga Replication Lag tuntas...");
  await sleep(350);

  const laterRes = await router.getUserWithSessionConsistency(userId);
  console.log(` - Hasil Baca: Nama = "${laterRes.data.name}"`);
  console.log(` - Sumber    : ${laterRes.source}`);
  console.log(` ✅ SUKSES! Setelah masa tenggang lewat, query kembali aman dibebankan ke Replica.`);

  console.log("\n===================================================================");
  console.log(" [KESIMPULAN DEMO]:");
  console.log(" 1. Replikasi asinkron selalu menyisakan jendela waktu 'Replication Lag'.");
  console.log(" 2. Mengarahkan penulisan ke Primary dan pembacaan naif ke Replica memicu");
  console.log("    anomali 'Read-Your-Own-Writes Inconsistency'.");
  console.log(" 3. Session Consistency melindungi pengalaman pengguna dengan 'sticky primary'");
  console.log("    selama beberapa ratus milidetik pasca transaksi penulisan.");
  console.log("===================================================================\n");
  process.exit(0);
}

runDemo();
