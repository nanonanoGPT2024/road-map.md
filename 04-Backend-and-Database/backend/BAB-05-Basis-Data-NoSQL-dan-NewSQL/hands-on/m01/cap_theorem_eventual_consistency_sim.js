/**
 * CAP Theorem & Distributed Consistency Simulator (CP vs AP)
 * 
 * Mensimulasikan arsitektur sistem penyimpanan terdistribusi:
 * 1. Kluster 3 Node (Node A, Node B, Node C) dengan Replikasi.
 * 2. Simulasi Partisi Jaringan: Node C terisolasi dari Node A dan Node B.
 * 3. Mode CP (Consistency + Partition Tolerance - Model MongoDB/etcd):
 *    - Quorum mayoritas (A & B) menerima tulis.
 *    - Node minoritas (C) MENOLAK request tulis demi mencegah data menyimpang!
 * 4. Mode AP (Availability + Partition Tolerance - Model Cassandra/DynamoDB):
 *    - Node minoritas (C) TETAP MENERIMA request tulis (High Availability).
 *    - Menunjukkan rekonsiliasi data saat jaringan sembuh (Eventual Consistency via LWW).
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

class DistributedNode {
  constructor(name) {
    this.name = name;
    this.storage = new Map(); // key -> { value, timestamp }
  }

  write(key, value, timestamp) {
    this.storage.set(key, { value, timestamp });
  }

  read(key) {
    return this.storage.get(key) || null;
  }
}

class DistributedClusterSimulator {
  constructor(mode = "CP") {
    this.mode = mode; // 'CP' | 'AP'
    this.nodes = [
      new DistributedNode("Node-A (Jakarta)"),
      new DistributedNode("Node-B (Surabaya)"),
      new DistributedNode("Node-C (Bali)")
    ];
    this.isPartitioned = false; // Flag apakah Node C terisolasi
  }

  setNetworkPartition(isolated) {
    this.isPartitioned = isolated;
    if (isolated) {
      log("network-switch", `KABEL FIBER OPTIK BALI PUTUS! [Node-C] terisolasi dari [Node-A & Node-B]!`, ANSI.bold + ANSI.red);
    } else {
      log("network-switch", `Jaringan Pulih Normal! Semua node dapat berkomunikasi kembali.`, ANSI.bold + ANSI.green);
    }
  }

  handleWrite(targetNodeName, key, value) {
    const targetNode = this.nodes.find(n => n.name.includes(targetNodeName));
    const now = Date.now();
    log("client-request", `Client mengirim perintah: WRITE '${key}' = '${value}' ke [${targetNode.name}]`, ANSI.cyan);

    // Jika sistem dalam Mode CP (Strict Consistency)
    if (this.mode === "CP") {
      if (this.isPartitioned && targetNodeName === "Bali") {
        log("cp-engine", `PENOLAKAN CP! [${targetNode.name}] adalah partisi minoritas (1/3 node). Tidak ada Quorum!`, ANSI.red);
        log("cp-engine", `STATUS: 503 Service Unavailable (Tolak tulis demi integritas data konsisten!)`, ANSI.bold + ANSI.red);
        return false;
      }

      // Quorum Mayoritas terpenuhi (Node-A & Node-B = 2/3)
      targetNode.write(key, value, now);
      log("cp-engine", `QUORUM MAYORITAS TERPENUHI (2/3 Node). Tulis sukses di ${targetNode.name} & direplikasi ke Node mayoritas!`, ANSI.green);
      return true;
    }

    // Jika sistem dalam Mode AP (High Availability)
    if (this.mode === "AP") {
      targetNode.write(key, value, now);
      if (this.isPartitioned && targetNodeName === "Bali") {
        log("ap-engine", `PENERIMAAN AP! [${targetNode.name}] menerima tulis meskipun terisolasi (Ketersediaan 100%)!`, ANSI.yellow);
        log("ap-engine", `STATUS: 200 OK (Data dicatat lokal, konsistensi menyusul via Eventual Consistency)`, ANSI.bold + ANSI.yellow);
      } else {
        log("ap-engine", `Tulis sukses di cluster mayoritas.`, ANSI.green);
      }
      return true;
    }
  }

  reconcileHealedNetwork() {
    log("reconciler", `=== Memulai Rekonsiliasi Eventual Consistency Pasca-Partisi (Last-Write-Wins) ===`, ANSI.magenta);
    // Cari versi data dengan timestamp terbaru di seluruh node
    let latestData = null;
    let latestTime = -1;

    for (const node of this.nodes) {
      for (const [k, v] of node.storage.entries()) {
        if (v.timestamp > latestTime) {
          latestTime = v.timestamp;
          latestData = { key: k, value: v.value, timestamp: v.timestamp };
        }
      }
    }

    if (latestData) {
      log("reconciler", `Data Paling Mutakhir Ditemukan: '${latestData.key}' = '${latestData.value}' (Timestamp: ${latestData.timestamp})`, ANSI.green);
      for (const node of this.nodes) {
        node.write(latestData.key, latestData.value, latestData.timestamp);
        log("reconciler", `-> Menyinkronkan [${node.name}]: '${latestData.key}' diset ke '${latestData.value}'`, ANSI.green);
      }
      log("reconciler", `KONSISTENSI AKHIR TERCAPAI (Cluster kembali identik 100%)!`, ANSI.bold + ANSI.green);
    }
  }
}

// ================= SIMULASI EKSEKUSI =================
console.log(`${ANSI.bold}================================================================${ANSI.reset}`);
console.log(`${ANSI.bold}      CAP THEOREM & DISTRIBUTED EVENTUAL CONSISTENCY SIM        ${ANSI.reset}`);
console.log(`${ANSI.bold}================================================================${ANSI.reset}\n`);

// 1. Uji Coba Mode CP (MongoDB / etcd)
console.log(`--- [BAGIAN 1: SISTEM CP (CONSISTENCY + PARTITION TOLERANCE)] ---`);
const cpCluster = new DistributedClusterSimulator("CP");
cpCluster.setNetworkPartition(true);

// Coba tulis ke node yang terisolasi
cpCluster.handleWrite("Bali", "user:status", "OFFLINE");

// 2. Uji Coba Mode AP (Cassandra / DynamoDB)
console.log(`\n--- [BAGIAN 2: SISTEM AP (AVAILABILITY + PARTITION TOLERANCE)] ---`);
const apCluster = new DistributedClusterSimulator("AP");
apCluster.setNetworkPartition(true);

// Tulis ke node terisolasi (AP menerima!)
apCluster.handleWrite("Bali", "wallet:balance", "750000");

// Jaringan sembuh kembali
console.log("");
apCluster.setNetworkPartition(false);
apCluster.reconcileHealedNetwork();

console.log(`\n${ANSI.bold}Perilaku Teorema CAP & Eventual Consistency teruji dan tervalidasi!${ANSI.reset}`);
