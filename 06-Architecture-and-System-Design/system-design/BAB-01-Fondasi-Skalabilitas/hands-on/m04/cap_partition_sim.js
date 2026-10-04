// cap_partition_sim.js
// Simulator Partisi Jaringan, Quorum Consensus (W + R > N), dan Trade-off CP vs AP

class DistributedNode {
  constructor(id) {
    this.id = id;
    this.storage = { balance: 100, version: 1 };
    this.isolated = false; // Status konektivitas jaringan
  }

  write(newBalance, newVersion) {
    if (this.isolated) {
      throw new Error(`[Node ${this.id}] Tidak dapat dijangkau (Network Partition)!`);
    }
    this.storage.balance = newBalance;
    this.storage.version = newVersion;
    return true;
  }

  read() {
    if (this.isolated) {
      throw new Error(`[Node ${this.id}] Tidak dapat dijangkau (Network Partition)!`);
    }
    return { ...this.storage };
  }
}

class DistributedCluster {
  constructor() {
    // Cluster 3 Node (N = 3)
    this.nodes = [
      new DistributedNode(1),
      new DistributedNode(2),
      new DistributedNode(3)
    ];
    this.currentVersion = 1;
  }

  // Simulasi Partisi Jaringan: Node 1 terisolasi di sisi lain partisi
  triggerNetworkPartition() {
    console.log("\n⚡ [PERISTIWA]: Terjadi Partisi Jaringan!");
    console.log("   -> Node 1 terisolasi di Zona Terpencil (Minority Partition).");
    console.log("   -> Node 2 dan Node 3 tetap terhubung (Majority Partition Quorum).\n");
    this.nodes[0].isolated = true;
    this.nodes[1].isolated = false;
    this.nodes[2].isolated = false;
  }

  healNetwork() {
    console.log("\n🔌 [PERISTIWA]: Partisi Jaringan Pulih. Seluruh node terhubung kembali.\n");
    this.nodes.forEach(n => n.isolated = false);
  }

  // Eksekusi Write dengan Mode CP (Strict Quorum: butuh mayoritas > N/2 = 2 node)
  executeWriteCP(newBalance) {
    console.log(`[MODE CP]: Mencoba Write Saldo Baru = $${newBalance} dengan Quorum Mayoritas (W = 2)...`);
    this.currentVersion++;
    let acks = 0;

    for (const node of this.nodes) {
      try {
        node.write(newBalance, this.currentVersion);
        acks++;
        console.log(`  -> Node ${node.id} berhasil menulis v${this.currentVersion} (Saldo: $${newBalance})`);
      } catch (err) {
        console.log(`  -> Node ${node.id} GAGAL: ${err.message}`);
      }
    }

    const majorityQuorum = Math.floor(this.nodes.length / 2) + 1; // 2 node
    if (acks >= majorityQuorum) {
      console.log(`  ✅ WRITE SUKSES! (${acks}/${this.nodes.length} node mengonfirmasi. Quorum tercapai). Data Aman Konsisten.`);
      return true;
    } else {
      console.log(`  ❌ WRITE DITOLAK! (${acks}/${this.nodes.length} node. Quorum gagal). Sistem memilih Konsistensi di atas Availability.`);
      return false;
    }
  }

  // Eksekusi Write dengan Mode AP (Weak Write: Cukup 1 node lokal berhasil)
  executeWriteAP(nodeId, newBalance) {
    console.log(`[MODE AP]: Mencoba Write ke Node ${nodeId} spesifik (Saldo: $${newBalance}) tanpa menunggu Quorum...`);
    const targetNode = this.nodes.find(n => n.id === nodeId);
    this.currentVersion++;
    try {
      // Pada sistem AP, node terisolasi tetap menerima penulisan lokal
      targetNode.storage.balance = newBalance;
      targetNode.storage.version = this.currentVersion;
      console.log(`  ✅ WRITE DITERIMA oleh Node ${nodeId}! (Memprioritaskan Ketersediaan Layanan).`);
      return true;
    } catch (err) {
      console.log(`  ❌ WRITE GAGAL: ${err.message}`);
      return false;
    }
  }

  printClusterState() {
    console.log("┌─────────────────────────────────────────────────────────────┐");
    console.log("│                    STATUS DATA CLUSTER                      │");
    console.log("├────────┬────────────┬─────────────┬───────────┬─────────────┤");
    console.log("│ Node   │ Status     │ Saldo ($)   │ Versi     │ Konsisten?  │");
    console.log("├────────┼────────────┼─────────────┼───────────┼─────────────┤");
    this.nodes.forEach(n => {
      const status = n.isolated ? 'TERISOLASI' : 'TERHUBUNG ';
      console.log(`│ Node ${n.id} │ ${status} │ $${n.storage.balance.toString().padEnd(10, ' ')}│ v${n.storage.version.toString().padEnd(9, ' ')}│ ${n.storage.version === this.currentVersion ? 'UP-TO-DATE ' : 'DATA USANG '}│`);
    });
    console.log("└────────┴────────────┴─────────────┴───────────┴─────────────┘");
  }
}

function main() {
  console.log("===================================================================");
  console.log("     SIMULATOR CAP THEOREM: DEMONSTRASI TRADE-OFF CP vs AP         ");
  console.log("===================================================================");

  const cluster = new DistributedCluster();
  console.log("\n[KONDISI AWAL]: Seluruh node sehat dan sinkron.");
  cluster.printClusterState();

  // Langkah 1: Terjadi Partisi
  cluster.triggerNetworkPartition();

  // Langkah 2: Uji Mode CP
  console.log("--- PENGUJIAN 1: SISTEM CP (Consistency & Partition Tolerance) ---");
  cluster.executeWriteCP(150);
  cluster.printClusterState();

  // Langkah 3: Uji Skenario AP yang memicu Write Conflict (Data Divergence)
  console.log("\n--- PENGUJIAN 2: SISTEM AP (Availability & Partition Tolerance) ---");
  console.log("User di zona Node 1 (terisolasi) memaksa transaksi penulisan:");
  cluster.executeWriteAP(1, 500); // Node 1 menulis saldo 500
  console.log("User di zona Node 2 (mayoritas) melakukan transaksi penulisan lain:");
  cluster.executeWriteAP(2, 200); // Node 2 menulis saldo 200
  cluster.printClusterState();

  console.log("\n[KESIMPULAN ARSITEKTURAL]:");
  console.log("1. Pada Mode CP: Node 1 yang terisolasi diabaikan, namun Quorum mayoritas (Node 2 & 3)");
  console.log("   menjamin data tidak mengalami percabangan (No Data Split).");
  console.log("2. Pada Mode AP: Kedua sisi partisi menerima transaksi, menghasilkan INKONSISTENSI DATA");
  console.log("   (Node 1 mencatat $500, Node 2 mencatat $200). Membutuhkan rekonsiliasi manual atau CRDT!\n");
}

main();
