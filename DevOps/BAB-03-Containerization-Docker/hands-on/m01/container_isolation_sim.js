/**
 * Hands-on M01: Linux Namespaces, Cgroups Quota, & Container OOM Killer Simulator
 * Mengilustrasikan konsep internal Docker/runc:
 * 1. PID & Network Namespace Mapping (Host PID vs Container PID 1)
 * 2. Cgroups Memory Quota & OOM Killer Enforcement (Exit Code 137)
 * 3. Security Non-Root Execution Enforcement (UID/GID)
 *
 * Jalankan: node container_isolation_sim.js
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

class SimulatedContainerRuntime {
  constructor() {
    this.containers = new Map();
    this.hostPidSequence = 10000;
  }

  // Membuat container baru dengan Namespaces & Cgroups
  createContainer(name, config = {}) {
    const hostPid = this.hostPidSequence++;
    const containerId = 'cnt_' + Math.random().toString(36).substring(2, 9);
    
    const container = {
      id: containerId,
      name,
      image: config.image || 'node:20-alpine',
      user: config.user || { uid: 1000, username: 'appuser' },
      
      // Linux Namespaces
      namespaces: {
        pid: { containerPid: 1, hostPid: hostPid },
        net: { veth: `veth_${containerId.substring(4, 8)}`, ip: `172.17.0.${this.containers.size + 2}` },
        mnt: { rootfs: `/var/lib/docker/overlay2/${containerId}/merged` }
      },

      // Linux Cgroups Limits
      cgroups: {
        memoryMaxMb: config.memoryMaxMb || 256,
        currentMemoryMb: 32,
        cpuQuotaPct: config.cpuQuotaPct || 100
      },

      state: 'RUNNING',
      exitCode: null
    };

    this.containers.set(containerId, container);
    console.log(`${colors.green}[CONTAINER CREATED] "${name}" (ID: ${containerId})${colors.reset}`);
    console.log(`  -> Namespaces : PID 1 (Host PID: ${hostPid}) | IP: ${container.namespaces.net.ip}`);
    console.log(`  -> User Model : UID ${container.user.uid} (${container.user.username}) - ${container.user.uid === 0 ? colors.red + 'ROOT DANGER!' : colors.green + 'Non-Root Safe'}${colors.reset}`);
    console.log(`  -> Cgroups    : Memory Limit: ${container.cgroups.memoryMaxMb}MB | CPU Quota: ${container.cgroups.cpuQuotaPct}%\n`);

    return container;
  }

  // Simulasi alokasi memori oleh proses di dalam container
  allocateMemory(containerId, additionalMb) {
    const cnt = this.containers.get(containerId);
    if (!cnt || cnt.state !== 'RUNNING') return;

    cnt.cgroups.currentMemoryMb += additionalMb;
    console.log(`  [ALLOCATE] ${cnt.name} mengalokasikan +${additionalMb}MB RAM (Total: ${cnt.cgroups.currentMemoryMb}MB / ${cnt.cgroups.memoryMaxMb}MB)`);

    // Cgroups Memory Max Check (Kernel Enforced)
    if (cnt.cgroups.currentMemoryMb > cnt.cgroups.memoryMaxMb) {
      console.log(`\n${colors.red}[KERNEL OOM KILLER TRIGGERED]${colors.reset}`);
      console.log(`  Proses di container "${cnt.name}" melampaui cgroup memory.max (${cnt.cgroups.currentMemoryMb}MB > ${cnt.cgroups.memoryMaxMb}MB)!`);
      console.log(`  Kernel mengirim sinyal SIGKILL paksa ke Host PID ${cnt.namespaces.pid.hostPid}...`);
      
      cnt.state = 'OOMKilled';
      cnt.exitCode = 137; // 128 + 9 (SIGKILL)
      cnt.cgroups.currentMemoryMb = 0;
      console.log(`  ${colors.red}[CONTAINER TERMINATED] Status: OOMKilled (Exit Code 137)${colors.reset}\n`);
    }
  }

  status(containerId) {
    const cnt = this.containers.get(containerId);
    if (!cnt) return;
    console.log(`* Status [${cnt.name}]: ${cnt.state} (Exit Code: ${cnt.exitCode !== null ? cnt.exitCode : 'Running'})`);
  }
}

// ==========================================
// TEST SCENARIOS
// ==========================================
async function runLab() {
  console.log(`${colors.bold}${colors.cyan}=== DEVOPS LAB: CONTAINER NAMESPACES & CGROUPS OOM ===${colors.reset}\n`);

  const runtime = new SimulatedContainerRuntime();

  // 1. Container Normal (Non-Root & Mematuhi Cgroups)
  console.log('--- 1. SPAWN HEALTHY CONTAINER (BEST PRACTICE) ---');
  const webApp = runtime.createContainer('frontend-ui', {
    image: 'nginx:alpine',
    user: { uid: 1000, username: 'nginx' },
    memoryMaxMb: 128,
    cpuQuotaPct: 50
  });

  runtime.allocateMemory(webApp.id, 40);
  runtime.status(webApp.id);

  // 2. Container dengan Memory Leak -> Memicu OOMKilled
  console.log('\n--- 2. SIMULASI MEMORY LEAK & KERNEL OOM KILLER ---');
  const workerApp = runtime.createContainer('data-processor', {
    image: 'python:3.11-slim',
    user: { uid: 1001, username: 'pyworker' },
    memoryMaxMb: 256
  });

  runtime.allocateMemory(workerApp.id, 100);
  runtime.allocateMemory(workerApp.id, 100);
  // Lonjakan beban memicu batas 256MB
  runtime.allocateMemory(workerApp.id, 80); // 32 + 100 + 100 + 80 = 312MB > 256MB

  runtime.status(workerApp.id);

  console.log(`${colors.bold}${colors.green}=== SEMUA SIMULASI NAMESPACES & CGROUPS SELESAI DENGAN SUKSES ===${colors.reset}`);
}

runLab();
