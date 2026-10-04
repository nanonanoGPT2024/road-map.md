/**
 * Linux Namespaces, Cgroups v2, OOM-Killer & OverlayFS Simulator
 * Hands-on Lab: BAB 01 - Module 02
 * 
 * Demonstrates:
 * 1. PID & Network Namespace Virtualization.
 * 2. Cgroups v2 Memory Limit & Kernel OOM Killer (Exit Code 137).
 * 3. Cgroups v2 PIDs Governor (Fork Bomb Prevention).
 * 4. OverlayFS Union Mount & Copy-on-Write (CoW) Mechanism.
 */

class NamespaceSimulator {
  static createProcess(command, hostPid) {
    return {
      command,
      hostPid,
      containerPid: 1, // Isolated PID Namespace view
      hostname: 'isolated-container-node',
      networkInterface: 'veth0_container (IP: 172.17.0.2)'
    };
  }
}

class CgroupsV2Governor {
  constructor(memoryLimitMb = 100, maxPids = 5) {
    this.memoryLimitMb = memoryLimitMb;
    this.maxPids = maxPids;
    this.currentMemoryMb = 10;
    this.activePids = 1; // PID 1 is running
  }

  allocateMemory(mb) {
    this.currentMemoryMb += mb;
    console.log(`[Cgroup Memory] Consuming +${mb}MB. Current: ${this.currentMemoryMb}MB / Limit: ${this.memoryLimitMb}MB`);

    if (this.currentMemoryMb > this.memoryLimitMb) {
      console.error(`💥 [KERNEL OOM KILLER TRIGGERED!] Container exceeded memory.max (${this.memoryLimitMb}MB)!`);
      console.error(`   ↳ Kernel sends SIGKILL (Signal 9) to Container PID 1.`);
      return {
        terminated: true,
        exitCode: 137, // 128 + 9 = 137 (Standard Linux OOM exit code)
        oomKilled: true
      };
    }
    return { terminated: false, exitCode: 0, oomKilled: false };
  }

  spawnProcess() {
    if (this.activePids >= this.maxPids) {
      console.error(`🚫 [CGROUP PIDS LIMIT EXCEEDED] Current active PIDs: ${this.activePids} reaches pids.max (${this.maxPids})!`);
      console.error(`   ↳ Syscall clone() REJECTED: EAGAIN (Resource temporarily unavailable - Fork bomb mitigated).`);
      return false;
    }
    this.activePids++;
    console.log(`[Cgroup PIDs] Spawned child process. Active PIDs: ${this.activePids}/${this.maxPids}`);
    return true;
  }
}

class OverlayFSSimulator {
  constructor() {
    // Read-only image layers
    this.lowerDir = {
      '/etc/os-release': 'NAME="Alpine Linux"\nVERSION="3.19"',
      '/bin/sh': '[BINARY: busybox sh]'
    };
    // Read-write container layer
    this.upperDir = {};
    // Whiteout markers for deleted files
    this.whiteouts = new Set();
  }

  // Reading a file checks upperDir first, then falls back to lowerDir
  readFile(path) {
    if (this.whiteouts.has(path)) {
      return null; // File marked as deleted
    }
    if (this.upperDir[path] !== undefined) {
      console.log(`📖 [OverlayFS Read] '${path}' read from UPPERDIR (Modified copy).`);
      return this.upperDir[path];
    }
    if (this.lowerDir[path] !== undefined) {
      console.log(`📖 [OverlayFS Read] '${path}' read from LOWERDIR (Read-only image layer).`);
      return this.lowerDir[path];
    }
    return null;
  }

  // Modifying or creating a file triggers Copy-on-Write (CoW)
  writeFile(path, content) {
    if (this.lowerDir[path] !== undefined && this.upperDir[path] === undefined) {
      console.log(`⚡ [Copy-on-Write (CoW)] File '${path}' exists in LowerDir. Copying up to UpperDir before modifying...`);
    } else {
      console.log(`✍️  [OverlayFS Write] Writing new file '${path}' directly to UPPERDIR.`);
    }
    this.upperDir[path] = content;
    this.whiteouts.delete(path);
  }

  // Deleting a file creates a whiteout marker in upperDir without touching lowerDir
  deleteFile(path) {
    console.log(`🗑️  [OverlayFS Delete] Creating whiteout marker for '${path}' in UPPERDIR. LowerDir remains UNTOUCHED.`);
    delete this.upperDir[path];
    this.whiteouts.add(path);
  }

  getMergedView() {
    const files = new Set([...Object.keys(this.lowerDir), ...Object.keys(this.upperDir)]);
    const merged = {};
    for (const f of files) {
      if (!this.whiteouts.has(f)) {
        merged[f] = this.upperDir[f] !== undefined ? this.upperDir[f] : this.lowerDir[f];
      }
    }
    return merged;
  }
}

// -----------------------------------------------------------------
// LAB SIMULATION
// -----------------------------------------------------------------
async function runLab() {
  console.log(`======================================================`);
  console.log(`🐧 LINUX PRIMITIVES & OVERLAYFS STORAGE LAB`);
  console.log(`======================================================\n`);

  // PART 1: Namespaces Virtualization
  console.log(`--- PART 1: NAMESPACES PROCESS VIRTUALIZATION ---`);
  const proc = NamespaceSimulator.createProcess('/usr/sbin/nginx', 29481);
  console.log(`Host Perspective      : Process PID = ${proc.hostPid}`);
  console.log(`Container Perspective : Process PID = ${proc.containerPid} (Isolated PID Namespace)`);
  console.log(`Isolated Network      : ${proc.networkInterface}`);
  console.log(`Isolated Hostname     : ${proc.hostname}\n`);

  // PART 2: Cgroups v2 & OOM Killer Simulation
  console.log(`--- PART 2: CGROUPS V2 MEMORY LIMIT & OOM KILLER ---`);
  const cgroup = new CgroupsV2Governor(100, 4); // 100MB limit, max 4 PIDs
  cgroup.allocateMemory(30);
  cgroup.allocateMemory(40);
  // This allocation will breach 100MB limit
  const oomResult = cgroup.allocateMemory(45);
  console.log(`Process State after Memory Breach:`, oomResult);

  // PART 3: Fork Bomb Mitigation
  console.log(`\n--- PART 3: CGROUPS V2 PIDS GOVERNOR (FORK BOMB DEFENSE) ---`);
  const forkCgroup = new CgroupsV2Governor(512, 4);
  console.log(`Simulating recursive thread creation (:(){ :|:& };:)...`);
  forkCgroup.spawnProcess(); // PID 2
  forkCgroup.spawnProcess(); // PID 3
  forkCgroup.spawnProcess(); // PID 4
  forkCgroup.spawnProcess(); // PID 5 (Exceeds max 4!)

  // PART 4: OverlayFS Union Mount & Copy-on-Write
  console.log(`\n--- PART 4: OVERLAYFS UNION MOUNT & COPY-ON-WRITE (CoW) ---`);
  const fs = new OverlayFSSimulator();

  // 1. Initial read from lowerDir
  console.log(`Initial read:`, fs.readFile('/etc/os-release'));

  // 2. Modifying file triggers CoW
  fs.writeFile('/etc/os-release', 'NAME="Custom Hardened OS"\nVERSION="2026"');
  console.log(`Read after modification:`, fs.readFile('/etc/os-release'));

  // 3. Deleting a file in container
  fs.deleteFile('/bin/sh');

  console.log(`\nFinal Merged View of Container Filesystem:`);
  console.log(fs.getMergedView());

  console.log(`\n🎉 Linux Namespaces, Cgroups, & OverlayFS Lab Complete!`);
}

runLab();
