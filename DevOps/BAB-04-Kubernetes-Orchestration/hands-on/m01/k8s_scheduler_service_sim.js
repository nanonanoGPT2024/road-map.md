/**
 * Hands-on M01: Kubernetes Reconciliation Loop, Scheduler, & Zero-Downtime RollingUpdate Simulator
 * Mengilustrasikan konsep:
 * 1. Control Plane Reconciliation Loop (Desired State vs Current State)
 * 2. Kube-Scheduler Node Placement berdasar kapasitas CPU/RAM
 * 3. RollingUpdate Zero Downtime (maxSurge=1, maxUnavailable=0)
 * 4. Service ClusterIP Endpoint Routing
 *
 * Jalankan: node k8s_scheduler_service_sim.js
 */

const colors = {
  reset: '\x1b[0m',
  cyan: '\x1b[36m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  magenta: '\x1b[35m',
  red: '\x1b[31m',
  bold: '\x1b[1m'
};

class K8sClusterSimulator {
  constructor() {
    this.nodes = [
      { name: 'worker-node-01', cpuCapacity: 4000, memCapacity: 8192, cpuUsed: 0, memUsed: 0 },
      { name: 'worker-node-02', cpuCapacity: 4000, memCapacity: 8192, cpuUsed: 0, memUsed: 0 }
    ];
    this.pods = new Map(); // podName -> Pod Object
    this.serviceEndpoints = []; // list of healthy Pod IPs
    this.clusterIp = '10.96.0.42';
  }

  // Kube-Scheduler: Memilih node terbaik dengan beban paling ringan
  schedulePod(pod) {
    const sortedNodes = [...this.nodes].sort((a, b) => (a.cpuUsed / a.cpuCapacity) - (b.cpuUsed / b.cpuCapacity));
    const targetNode = sortedNodes[0];

    targetNode.cpuUsed += pod.reqCpu;
    targetNode.memUsed += pod.reqMem;
    pod.node = targetNode.name;
    pod.ip = `10.244.${targetNode.name === 'worker-node-01' ? '1' : '2'}.${Math.floor(Math.random() * 200 + 10)}`;

    console.log(`  ${colors.cyan}[KUBE-SCHEDULER]${colors.reset} Pod ${pod.name} dijadwalkan ke ${targetNode.name} (IP: ${pod.ip})`);
    return targetNode;
  }

  // Membuat Pod dan mensimulasikan readiness probe
  async createPod(name, version, reqCpu = 200, reqMem = 256) {
    const pod = {
      name,
      version,
      reqCpu,
      reqMem,
      status: 'Pending',
      isReady: false,
      ip: null,
      node: null
    };

    this.schedulePod(pod);
    pod.status = 'ContainerCreating';
    this.pods.set(name, pod);

    // Simulasi startup container dan readiness probe (300ms)
    await new Promise(r => setTimeout(r, 300));
    pod.status = 'Running';
    pod.isReady = true;
    console.log(`  ${colors.green}[POD READY]${colors.reset} ${pod.name} (${pod.version}) berstatus RUNNING & Lulus ReadinessProbe!`);

    this.updateServiceEndpoints();
    return pod;
  }

  // Menghapus Pod dan melepaskan resource node
  deletePod(name) {
    const pod = this.pods.get(name);
    if (!pod) return;

    const node = this.nodes.find(n => n.name === pod.node);
    if (node) {
      node.cpuUsed -= pod.reqCpu;
      node.memUsed -= pod.reqMem;
    }

    this.pods.delete(name);
    console.log(`  ${colors.red}[POD TERMINATED]${colors.reset} ${name} (${pod.version}) dihapus secara tertib.`);
    this.updateServiceEndpoints();
  }

  // Service Endpoints Controller
  updateServiceEndpoints() {
    this.serviceEndpoints = Array.from(this.pods.values())
      .filter(p => p.isReady)
      .map(p => ({ pod: p.name, ip: p.port, version: p.version }));
  }

  // Simulasi Request via Service ClusterIP
  routeRequest(reqNum) {
    if (this.serviceEndpoints.length === 0) {
      console.log(`Req #${reqNum} -> ${colors.red}[503 Service Unavailable] Tidak ada Pod Ready!${colors.reset}`);
      return;
    }
    const target = this.serviceEndpoints[reqNum % this.serviceEndpoints.length];
    console.log(`Req #${reqNum} -> [Service: ${this.clusterIp}:80] Forwarded to ${target.pod} (${colors.yellow}${target.version}${colors.reset})`);
  }

  // RollingUpdate Controller Engine (maxSurge=1, maxUnavailable=0)
  async executeRollingUpdate(targetVersion, desiredReplicas = 3) {
    console.log(`\n${colors.bold}${colors.magenta}=== MEMULAI ZERO-DOWNTIME ROLLING UPDATE KE ${targetVersion} ===${colors.reset}`);
    console.log(`Strategi: maxSurge=1 (Boleh 4 pod saat transisi), maxUnavailable=0 (Minimal 3 pod selalu ready)\n`);

    const oldPods = Array.from(this.pods.values()).filter(p => p.version !== targetVersion);

    for (let i = 0; i < oldPods.length; i++) {
      const step = i + 1;
      console.log(`\n--- TRANSISI LANGKAH #${step} ---`);

      // 1. Buat 1 Pod baru (Surge +1)
      const newPodName = `app-deployment-${targetVersion}-${Math.random().toString(36).substring(2, 6)}`;
      await this.createPod(newPodName, targetVersion);

      // Verifikasi ketersediaan service saat transisi
      this.routeRequest(step * 10);

      // 2. Hapus 1 Pod lama setelah Pod baru ready
      const podToRemove = oldPods[i];
      this.deletePod(podToRemove.name);

      // Verifikasi ketersediaan service setelah Pod lama dihapus
      this.routeRequest(step * 10 + 1);
    }

    console.log(`\n${colors.bold}${colors.green}=== ROLLING UPDATE SELESAI 100% TANPA DOWNTIME ===${colors.reset}\n`);
  }
}

// ==========================================
// TEST SCENARIOS
// ==========================================
async function runLab() {
  console.log(`${colors.bold}${colors.cyan}=== DEVOPS LAB: KUBERNETES CONTROL PLANE & ROLLING UPDATE ===${colors.reset}\n`);

  const k8s = new K8sClusterSimulator();

  // 1. Deployment Awal (Versi v1.0 - 3 Replica)
  console.log('--- 1. INITIAL DEPLOYMENT (3 REPLICAS - v1.0) ---');
  await k8s.createPod('app-dep-v1-a1', 'v1.0');
  await k8s.createPod('app-dep-v1-b2', 'v1.0');
  await k8s.createPod('app-dep-v1-c3', 'v1.0');

  console.log('\nTesting Service ClusterIP Routing ke v1.0:');
  for (let i = 1; i <= 3; i++) k8s.routeRequest(i);

  // 2. Rolling Update ke v2.0 (Zero Downtime)
  await k8s.executeRollingUpdate('v2.0', 3);

  // 3. Final State Check
  console.log('--- STATUS AKHIR KUBERNETES CLUSTER ---');
  console.log(`Total Active Pods : ${k8s.pods.size}`);
  Array.from(k8s.pods.values()).forEach(p => {
    console.log(`  * ${p.name} | Version: ${p.version} | Node: ${p.node} | IP: ${p.ip} | Ready: ${p.isReady}`);
  });

  console.log('\nTesting Service Routing Pasca Upgrade (Harus 100% v2.0):');
  for (let i = 1; i <= 3; i++) k8s.routeRequest(i);

  console.log(`\n${colors.bold}${colors.green}=== SEMUA SIMULASI KUBERNETES SELESAI DENGAN SUKSES ===${colors.reset}`);
}

runLab();
