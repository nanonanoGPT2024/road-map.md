/**
 * Docker Engine Architecture & Live-Restore Simulator
 * Hands-on Lab: BAB 01 - Module 01
 * 
 * Demonstrates:
 * 1. Benchmark: Container (Process Isolation) vs VM (Full OS Virtualization).
 * 2. Execution Chain: CLI -> dockerd -> containerd -> containerd-shim -> runc.
 * 3. Live-Restore Demonstration: Killing dockerd without terminating active containers.
 */

const { EventEmitter } = require('events');

class VirtualMachineBenchmark {
  static boot() {
    const start = Date.now();
    // Simulate BIOS, Kernel decompress, systemd initialization, Guest OS RAM reservation
    const memoryOverheadMb = 1024; // 1 GB Guest OS baseline
    const bootTimeMs = 350; // scaled simulation
    return {
      type: 'Virtual Machine',
      bootTimeMs,
      memoryOverheadMb,
      isolation: 'Hardware Hypervisor Level'
    };
  }
}

class ContainerBenchmark {
  static start() {
    const start = Date.now();
    // Container starts as an isolated Linux process via clone() syscall
    const memoryOverheadMb = 14; // Minimal process overhead
    const bootTimeMs = 12; // Milliseconds
    return {
      type: 'Docker Container',
      bootTimeMs,
      memoryOverheadMb,
      isolation: 'OS-Level Namespaces & Cgroups'
    };
  }
}

class ContainerdShim extends EventEmitter {
  constructor(containerId, command) {
    super();
    this.containerId = containerId;
    this.command = command;
    this.pid = Math.floor(1000 + Math.random() * 9000);
    this.status = 'RUNNING';
    this.logs = [];
  }

  emitOutput(text) {
    this.logs.push(`[${new Date().toISOString()}] ${text}`);
  }
}

class DockerDaemonSimulator {
  constructor(liveRestore = true) {
    this.liveRestore = liveRestore;
    this.status = 'ONLINE';
    this.containers = new Map(); // id -> shim
  }

  async runContainer(image, command) {
    console.log(`\n[Docker CLI] $ docker run -d ${image} ${command}`);
    console.log(`[dockerd] Received HTTP POST /containers/create on /var/run/docker.sock`);
    await new Promise(r => setTimeout(r, 40));

    console.log(`[containerd] gRPC call -> Creating OCI container bundle for '${image}'`);
    await new Promise(r => setTimeout(r, 30));

    const containerId = Math.random().toString(16).substring(2, 10);
    const shim = new ContainerdShim(containerId, command);

    console.log(`[containerd-shim] Spawned shim PID ${shim.pid} to hold stdin/stdout/stderr`);
    console.log(`[runc] Invoked: runc create && runc start (configuring Linux kernel)`);
    console.log(`[runc] Execution complete. runc process EXITED immediately.`);

    shim.emitOutput(`App '${command}' running smoothly.`);
    this.containers.set(containerId, shim);

    console.log(`✅ [Container Started] ID: ${containerId} | PID: ${shim.pid} | Status: RUNNING`);
    return shim;
  }

  restartDaemon() {
    console.log(`\n⚠️  [ADMIN EVENT] Restarting Docker Daemon (dockerd)...`);
    this.status = 'RESTARTING';

    if (!this.liveRestore) {
      console.error(`🚨 [DOWNTIME] live-restore is FALSE! All running containers were KILLED by daemon shutdown!`);
      for (const shim of this.containers.values()) {
        shim.status = 'TERMINATED';
      }
    } else {
      console.log(`🛡️  [LIVE-RESTORE ACTIVE] dockerd disconnecting safely.`);
      console.log(`   containerd-shim is holding container processes alive in the kernel!`);
      for (const shim of this.containers.values()) {
        shim.emitOutput(`Handled traffic during dockerd downtime.`);
      }
    }

    this.status = 'ONLINE';
    console.log(`✅ [dockerd] Docker Daemon back ONLINE and reconnected to active shims.`);
  }
}

// -----------------------------------------------------------------
// LAB EXECUTION
// -----------------------------------------------------------------
async function runLab() {
  console.log(`======================================================`);
  console.log(`🐳 DOCKER ARCHITECTURE & ISOLATION BENCHMARK LAB`);
  console.log(`======================================================\n`);

  // Part 1: VM vs Container Comparison
  console.log(`--- PART 1: HARDWARE VM VS CONTAINER DENSITY BENCHMARK ---`);
  const vm = VirtualMachineBenchmark.boot();
  const ct = ContainerBenchmark.start();

  console.log(`1. ${vm.type.padEnd(18)}: Boot Time ~${vm.bootTimeMs}ms | RAM Overhead: ${vm.memoryOverheadMb} MB`);
  console.log(`2. ${ct.type.padEnd(18)}: Boot Time ~${ct.bootTimeMs}ms  | RAM Overhead: ${ct.memoryOverheadMb} MB`);
  console.log(`↳ Result: Containers are ${(vm.bootTimeMs / ct.bootTimeMs).toFixed(1)}x faster to start and consume ${((1 - (ct.memoryOverheadMb / vm.memoryOverheadMb)) * 100).toFixed(1)}% less memory overhead!\n`);

  // Part 2: Execution Chain (CLI -> dockerd -> containerd -> shim -> runc)
  console.log(`--- PART 2: THE RUNTIME EXECUTION CHAIN ---`);
  const daemon = new DockerDaemonSimulator(true); // live-restore enabled
  const webApp = await daemon.runContainer('nginx:alpine', 'nginx -g "daemon off;"');

  // Part 3: Live-Restore in Action
  console.log(`\n--- PART 3: SIMULATING DOCKER DAEMON REBOOT (LIVE-RESTORE) ---`);
  daemon.restartDaemon();

  console.log(`\nChecking Container ${webApp.containerId} Status: ${webApp.status}`);
  console.log(`Container Logs maintained by containerd-shim:`);
  webApp.logs.forEach(log => console.log(`   ↳ ${log}`));

  console.log(`\n🎉 Docker Architecture & Runtime Lab Completed Successfully!`);
}

runLab();
