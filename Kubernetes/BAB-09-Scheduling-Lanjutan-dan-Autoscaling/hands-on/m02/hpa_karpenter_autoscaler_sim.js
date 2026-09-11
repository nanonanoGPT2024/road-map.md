/**
 * Kubernetes HPA v2 & Karpenter Node Autoscaler Simulator
 * 
 * Mensimulasikan siklus autoscaling dua lapis end-to-end:
 * 1. Layer Workload: HPA v2 mengevaluasi metrik CPU dan menghitung desired replicas via rumus resmi.
 * 2. Stabilisasi Anti-Flapping: Jendela pendinginan scale-down.
 * 3. Layer Infrastruktur: Karpenter mendeteksi Pod Pending, menganalisis kebutuhan resource,
 *    melakukan bin-packing cerdas ke Spot/On-Demand catalog, dan melakukan konsolidasi otomatis.
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

// Model Katalog Cloud Instance (EC2 Catalog)
const EC2_CATALOG = [
  { type: "c6i.large", cpu: 2, memGi: 4, onDemandPrice: 0.085, spotPrice: 0.028 },
  { type: "c6i.xlarge", cpu: 4, memGi: 8, onDemandPrice: 0.170, spotPrice: 0.055 },
  { type: "c6i.2xlarge", cpu: 8, memGi: 16, onDemandPrice: 0.340, spotPrice: 0.110 },
  { type: "r6i.xlarge", cpu: 4, memGi: 32, onDemandPrice: 0.252, spotPrice: 0.080 }
];

class HPASimulator {
  constructor(deploymentName, minReplicas, maxReplicas, targetCpuPercent) {
    this.name = deploymentName;
    this.min = minReplicas;
    this.max = maxReplicas;
    this.targetCpu = targetCpuPercent;
    this.currentReplicas = minReplicas;
    this.scaleDownHistory = []; // Untuk stabilization window
  }

  evaluate(currentAvgCpu, timestampSec) {
    log("hpa-controller", `Evaluasi Metrik: Deployment '${this.name}', Current CPU: ${currentAvgCpu}%, Target CPU: ${this.targetCpu}%, Current Replicas: ${this.currentReplicas}`, ANSI.cyan);

    // Rumus Resmi HPA K8s
    const ratio = currentAvgCpu / this.targetCpu;
    let desired = Math.ceil(this.currentReplicas * ratio);

    // Enforce batas min dan max
    desired = Math.max(this.min, Math.min(this.max, desired));

    if (desired > this.currentReplicas) {
      log("hpa-controller", `TRAFFIC SPIKE DETECTED! Menghitung skala naik: ${this.currentReplicas} -> ${desired} Replika`, ANSI.green);
      this.currentReplicas = desired;
    } else if (desired < this.currentReplicas) {
      log("hpa-controller", `Traffic mereda. Desired: ${desired} Replika. Mengevaluasi jendela stabilisasi (anti-flapping 300s)...`, ANSI.yellow);
      this.scaleDownHistory.push({ time: timestampSec, desired });
      // Cek apakah stabil selama 300 detik
      const fiveMinAgo = timestampSec - 300;
      const validHistory = this.scaleDownHistory.filter(h => h.time >= fiveMinAgo);
      const maxDesiredInWindow = Math.max(...validHistory.map(h => h.desired));

      if (maxDesiredInWindow < this.currentReplicas) {
        log("hpa-controller", `Jendela stabilisasi terpenuhi! Menurunkan replika menjadi ${maxDesiredInWindow}`, ANSI.yellow);
        this.currentReplicas = maxDesiredInWindow;
      } else {
        log("hpa-controller", `Penurunan ditahan oleh stabilizationWindowSeconds untuk mencegah flapping.`, ANSI.yellow);
      }
    } else {
      log("hpa-controller", `Beban seimbang. Jumlah replika tetap ${this.currentReplicas}`, ANSI.cyan);
    }

    return this.currentReplicas;
  }
}

class KarpenterSimulator {
  constructor() {
    this.nodes = [];
  }

  reconcile(pendingPods) {
    if (pendingPods.length === 0) return;

    log("karpenter", `Mendeteksi ${pendingPods.length} Pod berstatus PENDING karena kapasitas node penuh!`, ANSI.yellow);
    
    // Hitung akumulasi resource yang dibutuhkan
    let totalReqCpu = 0;
    let totalReqMem = 0;
    for (const pod of pendingPods) {
      totalReqCpu += pod.cpu;
      totalReqMem += pod.mem;
    }

    log("karpenter", `Akumulasi Kebutuhan Pending Pods: ${totalReqCpu} Cores CPU, ${totalReqMem} GiB RAM`, ANSI.cyan);

    // Algoritma Bin-Packing Cerdas: Cari instance termurah yang sanggup menampung seluruh pod
    let bestInstance = null;
    let lowestCost = Infinity;

    for (const inst of EC2_CATALOG) {
      // Periksa apakah instance mampu menampung
      if (inst.cpu >= totalReqCpu && inst.memGi >= totalReqMem) {
        // Asumsikan preferensi Spot
        const cost = inst.spotPrice;
        if (cost < lowestCost) {
          lowestCost = cost;
          bestInstance = inst;
        }
      }
    }

    if (!bestInstance) {
      // Jika butuh lebih besar, pilih instance terbesar yang ada
      bestInstance = EC2_CATALOG[2]; // c6i.2xlarge
    }

    const newNodeId = `node-karpenter-${Math.random().toString(36).substring(2, 8)}`;
    log("karpenter", `Keputusan Bin-Packing: Meluncurkan 1x [${bestInstance.type}] (Spot $${bestInstance.spotPrice}/hr) - Lebih hemat 68% dibanding On-Demand!`, ANSI.green);
    log("karpenter", `Memanggil AWS EC2 CreateFleet API... (Estimasi waktu: 35 detik)`, ANSI.green);

    const newNode = {
      id: newNodeId,
      type: bestInstance.type,
      totalCpu: bestInstance.cpu,
      totalMem: bestInstance.memGi,
      usedCpu: totalReqCpu,
      usedMem: totalReqMem,
      pods: [...pendingPods]
    };

    this.nodes.push(newNode);
    log("karpenter", `Node '${newNodeId}' BERHASIL TERPASANG & READY! Semua ${pendingPods.length} Pod berhasil di-bind!`, ANSI.green);
  }

  consolidate() {
    log("karpenter", `=== Memeriksa Peluang Konsolidasi Node (Disruption Controller) ===`, ANSI.magenta);
    for (let i = this.nodes.length - 1; i >= 0; i--) {
      const node = this.nodes[i];
      if (node.pods.length === 0 || node.usedCpu === 0) {
        log("karpenter", `Konsolidasi: Node '${node.id}' kosong dan tidak memiliki pod aktif. Menghentikan instance untuk memangkas biaya cloud!`, ANSI.magenta);
        this.nodes.splice(i, 1);
      }
    }
  }
}

// ================= SIMULASI EKSEKUSI =================
console.log(`${ANSI.bold}================================================================${ANSI.reset}`);
console.log(`${ANSI.bold}     KUBERNETES HPA v2 & KARPENTER AUTOSCALER SIMULATION        ${ANSI.reset}`);
console.log(`${ANSI.bold}================================================================${ANSI.reset}\n`);

const hpa = new HPASimulator("ecommerce-checkout", 2, 10, 50);
const karpenter = new KarpenterSimulator();

// Baseline awal: 2 replika di node eksisting
let clusterAvailableCpu = 2; // Node lama hanya muat 2 pod

console.log("--- T = 00:00 (Kondisi Normal) ---");
hpa.evaluate(45, 0);

console.log("\n--- T = 00:15 (Flash Sale Dimulai: Lonjakan Traffic Drastis) ---");
// CPU melonjak ke 250% (5x target)
const desiredReplicas = hpa.evaluate(250, 15);

// Cek berapa pod yang muat di node eksisting
const existingRunningPods = 2;
const newlyCreatedPods = desiredReplicas - existingRunningPods;
const pendingPods = [];

log("kube-scheduler", `Mencoba menjadwalkan ${newlyCreatedPods} Pod baru...`, ANSI.cyan);
for (let i = 1; i <= newlyCreatedPods; i++) {
  const pod = { name: `checkout-pod-${i + 2}`, cpu: 1, mem: 2 };
  if (clusterAvailableCpu >= pod.cpu) {
    clusterAvailableCpu -= pod.cpu;
    log("kube-scheduler", `Pod ${pod.name} berhasil dijadwalkan di node eksisting.`, ANSI.cyan);
  } else {
    log("kube-scheduler", `Pod ${pod.name} PENDING (Insufficient CPU)!`, ANSI.red);
    pendingPods.push(pod);
  }
}

console.log("\n--- Karpenter Event-Driven Node Provisioning ---");
karpenter.reconcile(pendingPods);

console.log("\n--- T = 05:30 (Traffic Mereda: Flash Sale Selesai) ---");
// CPU turun drastis ke 20%
hpa.evaluate(20, 330);

// Simulasi eviksi pod yang di-scale down
if (karpenter.nodes.length > 0) {
  log("hpa-controller", `Menghentikan pod-pod tambahan di node Karpenter...`, ANSI.yellow);
  karpenter.nodes[0].pods = [];
  karpenter.nodes[0].usedCpu = 0;
}

karpenter.consolidate();

console.log(`\n${ANSI.bold}Simulasi Autoscaling HPA + Karpenter berhasil diselesaikan dengan sempurna!${ANSI.reset}`);
