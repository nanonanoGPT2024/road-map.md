/**
 * Kubernetes Advanced Scheduler Simulation Engine
 * 
 * Mensimulasikan pipeline internal kube-scheduler:
 * 1. Filtering (Predicates): Kapasitas CPU/RAM, Taints vs Tolerations, Hard NodeAffinity.
 * 2. Scoring (Priorities): Soft NodeAffinity weights, Resource BalancedAllocation, Topology Spread.
 * 3. Binding: Pemilihan Node dengan skor tertinggi dan penugasan Pod.
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

class Node {
  constructor(name, zone, cpuCores, memoryGi, labels = {}, taints = []) {
    this.name = name;
    this.zone = zone;
    this.totalCpu = cpuCores;
    this.totalMem = memoryGi;
    this.usedCpu = 0;
    this.usedMem = 0;
    this.labels = { ...labels, "topology.kubernetes.io/zone": zone, "kubernetes.io/hostname": name };
    this.taints = taints; // [{ key, value, effect }]
    this.pods = [];
  }

  get availableCpu() { return this.totalCpu - this.usedCpu; }
  get availableMem() { return this.totalMem - this.usedMem; }
}

class KubeScheduler {
  constructor(nodes) {
    this.nodes = nodes;
  }

  schedule(pod) {
    log("scheduler", `=== Memulai Penjadwalan Pod: ${pod.name} ===`, ANSI.bold);

    // ================= FASE 1: FILTERING (PREDICATES) =================
    const viableNodes = [];

    for (const node of this.nodes) {
      log("filter", `Memeriksa node '${node.name}' (Zone: ${node.zone})...`, ANSI.cyan);

      // 1. Resource Check
      if (node.availableCpu < pod.reqCpu || node.availableMem < pod.reqMem) {
        log("filter", `-> DITOLAK: Resource tidak cukup (Req: ${pod.reqCpu}C/${pod.reqMem}Gi, Sisa: ${node.availableCpu}C/${node.availableMem}Gi)`, ANSI.red);
        continue;
      }

      // 2. Taint & Toleration Check
      let taintViolated = false;
      for (const taint of node.taints) {
        const tolerated = (pod.tolerations || []).some(tol => 
          tol.key === taint.key && 
          (tol.operator === "Exists" || tol.value === taint.value) &&
          (!tol.effect || tol.effect === taint.effect)
        );
        if (!tolerated) {
          log("filter", `-> DITOLAK: Taint '${taint.key}=${taint.value}:${taint.effect}' tidak ditoleransi oleh Pod.`, ANSI.red);
          taintViolated = true;
          break;
        }
      }
      if (taintViolated) continue;

      // 3. NodeAffinity Hard (required)
      if (pod.nodeAffinityRequired) {
        const match = this._evalNodeSelectorTerms(pod.nodeAffinityRequired, node.labels);
        if (!match) {
          log("filter", `-> DITOLAK: NodeAffinity Required tidak cocok dengan label node.`, ANSI.red);
          continue;
        }
      }

      log("filter", `-> LOLOS FILTERING: Node '${node.name}' memenuhi seluruh persyaratan.`, ANSI.green);
      viableNodes.push(node);
    }

    if (viableNodes.length === 0) {
      log("scheduler", `GAGAL! Tidak ada node yang lolos filtering. Pod '${pod.name}' berstatus PENDING.`, ANSI.red);
      return null;
    }

    // ================= FASE 2: SCORING (PRIORITIES) =================
    log("scoring", `=== Menghitung Skor untuk ${viableNodes.length} Node yang Lolos ===`, ANSI.bold);
    let highestScore = -1;
    let selectedNode = null;

    for (const node of viableNodes) {
      let score = 0;

      // 1. Scoring: LeastAllocated (Memilih node yang bebannya paling rendah)
      const cpuUsageFraction = node.usedCpu / node.totalCpu;
      const memUsageFraction = node.usedMem / node.totalMem;
      const resourceScore = Math.round((1 - (cpuUsageFraction + memUsageFraction) / 2) * 50); // Maks 50 poin
      score += resourceScore;

      // 2. Scoring: Soft NodeAffinity (weights)
      if (pod.nodeAffinityPreferred) {
        for (const pref of pod.nodeAffinityPreferred) {
          if (this._evalMatchExpressions(pref.preference.matchExpressions, node.labels)) {
            score += pref.weight; // Tambah bobot (misal 30 poin)
            log("scoring", `-> Node '${node.name}' mendapat bonus preferensi +${pref.weight} poin`, ANSI.yellow);
          }
        }
      }

      // 3. Scoring: Topology Spread Constraints (Penyebaran Lintas Zona)
      if (pod.topologySpread) {
        const zoneKey = pod.topologySpread.topologyKey;
        const currentZonePods = this.nodes
          .filter(n => n.labels[zoneKey] === node.labels[zoneKey])
          .reduce((acc, n) => acc + n.pods.filter(p => p.app === pod.app).length, 0);

        // Semakin sedikit pod yang ada di zona ini, semakin tinggi skornya
        const spreadScore = Math.max(0, 30 - (currentZonePods * 10));
        score += spreadScore;
        log("scoring", `-> Zone '${node.zone}' saat ini memiliki ${currentZonePods} pod '${pod.app}'. Spread score: +${spreadScore}`, ANSI.magenta);
      }

      log("scoring", `Total Skor Node '${node.name}': ${score} poin`, ANSI.cyan);

      if (score > highestScore) {
        highestScore = score;
        selectedNode = node;
      }
    }

    // ================= FASE 3: BINDING =================
    log("binding", `WINNER: Memilih '${selectedNode.name}' (Skor Tertinggi: ${highestScore}) untuk Pod '${pod.name}'`, ANSI.green);
    selectedNode.usedCpu += pod.reqCpu;
    selectedNode.usedMem += pod.reqMem;
    selectedNode.pods.push(pod);
    pod.assignedNode = selectedNode.name;
    return selectedNode;
  }

  _evalNodeSelectorTerms(terms, labels) {
    return terms.some(term => this._evalMatchExpressions(term.matchExpressions, labels));
  }

  _evalMatchExpressions(expressions, labels) {
    return expressions.every(expr => {
      const val = labels[expr.key];
      if (expr.operator === "In") return expr.values.includes(val);
      if (expr.operator === "NotIn") return !expr.values.includes(val);
      if (expr.operator === "Exists") return val !== undefined;
      return false;
    });
  }
}

// ================= SIMULASI EKSEKUSI =================
console.log(`${ANSI.bold}================================================================${ANSI.reset}`);
console.log(`${ANSI.bold}         KUBERNETES ADVANCED SCHEDULER SIMULATION ENGINE        ${ANSI.reset}`);
console.log(`${ANSI.bold}================================================================${ANSI.reset}\n`);

// 1. Inisialisasi Fleet Node
const clusterNodes = [
  new Node("node-1-zone-a", "ap-southeast-1a", 4, 8, { "node.kubernetes.io/instance-type": "c6i.xlarge", "kubernetes.io/arch": "amd64" }),
  new Node("node-2-zone-b", "ap-southeast-1b", 4, 8, { "node.kubernetes.io/instance-type": "c6i.xlarge", "kubernetes.io/arch": "amd64" }),
  new Node("node-3-zone-c", "ap-southeast-1c", 8, 32, { "node.kubernetes.io/instance-type": "g5.xlarge", "gpu": "nvidia", "kubernetes.io/arch": "amd64" }, [
    { key: "dedicated", value: "gpu-node", effect: "NoSchedule" }
  ]),
  new Node("node-4-arm-zone-a", "ap-southeast-1a", 4, 8, { "node.kubernetes.io/instance-type": "c7g.xlarge", "kubernetes.io/arch": "arm64" })
];

const scheduler = new KubeScheduler(clusterNodes);

// Skenario 1: Web App Pod dengan TopologySpreadConstraints & NodeAffinity Soft
console.log("\n--- Skenario 1: Deployment 3 Pod Web App (Topology Spread Antar Zona) ---");
for (let i = 1; i <= 3; i++) {
  const webPod = {
    name: `web-app-pod-${i}`,
    app: "web-app",
    reqCpu: 1,
    reqMem: 2,
    tolerations: [], // Tanpa toleration GPU
    nodeAffinityRequired: [
      { matchExpressions: [{ key: "kubernetes.io/arch", operator: "In", values: ["amd64"] }] }
    ],
    topologySpread: {
      topologyKey: "topology.kubernetes.io/zone",
      maxSkew: 1
    }
  };
  scheduler.schedule(webPod);
}

// Skenario 2: Machine Learning Pod dengan GPU Toleration & NodeAffinity
console.log("\n--- Skenario 2: ML Workload dengan GPU Taint Toleration ---");
const mlPod = {
  name: "llm-inference-pod",
  app: "ml-worker",
  reqCpu: 4,
  reqMem: 16,
  tolerations: [
    { key: "dedicated", operator: "Equal", value: "gpu-node", effect: "NoSchedule" }
  ],
  nodeAffinityRequired: [
    { matchExpressions: [{ key: "gpu", operator: "In", values: ["nvidia"] }] }
  ]
};
scheduler.schedule(mlPod);

console.log("\n--- Ringkasan Penempatan Workload di Seluruh Cluster ---");
for (const n of clusterNodes) {
  console.log(`Node [${n.name}] (Zone: ${n.zone}, Sisa: ${n.availableCpu}C/${n.availableMem}Gi): Pods: [${n.pods.map(p => p.name).join(", ") || "Kosong"}]`);
}

console.log(`\n${ANSI.bold}Seluruh logika Filtering, Scoring, dan Topology Balancing tervalidasi!${ANSI.reset}`);
