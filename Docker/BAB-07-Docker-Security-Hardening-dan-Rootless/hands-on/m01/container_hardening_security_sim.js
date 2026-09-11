/**
 * Docker Container Hardening & Attack Defense Simulator
 * Hands-on Lab: BAB 07 - Module 01
 * 
 * Demonstrates:
 * 1. Privilege Escalation Mitigation: no-new-privileges: true.
 * 2. Linux Capabilities Dropping: --cap-drop=ALL blocks raw sockets.
 * 3. Read-Only Root Filesystem: Blocks web shell injection.
 * 4. Tmpfs Noexec: Blocks malware script execution from temporary RAM directory.
 */

class HardenedContainerSimulator {
  constructor(name, config = {}) {
    this.name = name;
    this.user = config.user || 0; // 0 = root, 10001 = non-root
    this.noNewPrivileges = config.noNewPrivileges || false;
    this.capabilities = new Set(config.capabilities || ['CAP_CHOWN', 'CAP_NET_RAW', 'CAP_SYS_ADMIN']);
    this.readOnlyRoot = config.readOnlyRoot || false;
    this.tmpfsNoexec = config.tmpfsNoexec || false;
  }

  // Attack 1: Exploit SUID binary (e.g. sudo / setuid) to elevate to root
  attemptPrivilegeEscalation() {
    console.log(`\n🎯 [Attack 1: SUID Privilege Escalation] Running setuid exploit inside ${this.name}...`);
    if (this.user === 0) {
      console.warn(`⚠️  [EXPLOIT SUCCESSFUL] Process is ALREADY ROOT (UID 0). Attacker has full container power!`);
      return true;
    }
    if (this.noNewPrivileges) {
      console.log(`🛡️  [DEFENSE BLOCKED] Kernel refused setuid execution! (no-new-privileges: true enforced).`);
      console.log(`   ↳ Attacker is stuck as unprivileged UID ${this.user}.`);
      return false;
    }
    console.warn(`⚠️  [EXPLOIT SUCCESSFUL] Attacker elevated from UID ${this.user} to ROOT via vulnerable SUID binary!`);
    return true;
  }

  // Attack 2: Raw Network Socket Spoofing / Packet Sniffing
  attemptRawNetworkAccess() {
    console.log(`\n🎯 [Attack 2: Raw Network Socket Spoofing] Calling socket(AF_INET, SOCK_RAW)...`);
    if (!this.capabilities.has('CAP_NET_RAW')) {
      console.log(`🛡️  [DEFENSE BLOCKED] Syscall failed with EPERM: Operation not permitted!`);
      console.log(`   ↳ Blocked by --cap-drop=ALL. Container cannot forge raw packets.`);
      return false;
    }
    console.warn(`⚠️  [EXPLOIT SUCCESSFUL] Raw socket opened! Attacker can sniff local bridge traffic.`);
    return true;
  }

  // Attack 3: Persist Web Shell to Filesystem (/var/www/shell.php)
  attemptWriteWebShell() {
    console.log(`\n🎯 [Attack 3: Injecting Web Shell] Writing exploit script to /var/www/shell.php...`);
    if (this.readOnlyRoot) {
      console.log(`🛡️  [DEFENSE BLOCKED] Filesystem write failed: EROFS (Read-only file system)!`);
      console.log(`   ↳ Protected by --read-only. Web shell rejected.`);
      return false;
    }
    console.warn(`⚠️  [EXPLOIT SUCCESSFUL] Web shell saved! Attacker establishes permanent backdoor.`);
    return true;
  }

  // Attack 4: Download and execute malware binary in /tmp
  attemptExecuteMalwareInTmp() {
    console.log(`\n🎯 [Attack 4: Execute Crypto Miner in /tmp] Running /tmp/crypto_miner...`);
    if (this.tmpfsNoexec) {
      console.log(`🛡️  [DEFENSE BLOCKED] Execution failed: Permission Denied!`);
      console.log(`   ↳ Blocked by --tmpfs /tmp:noexec. Binaries cannot be executed from RAM disk.`);
      return false;
    }
    console.warn(`⚠️  [EXPLOIT SUCCESSFUL] Crypto miner process spawned! Consuming 100% CPU.`);
    return true;
  }
}

// -----------------------------------------------------------------
// LAB SIMULATION
// -----------------------------------------------------------------
async function runLab() {
  console.log(`======================================================`);
  console.log(`🛡️  DOCKER SECURITY HARDENING & DEFENSE SIMULATOR`);
  console.log(`======================================================\n`);

  // BENCHMARK 1: Default Insecure Container
  console.log(`>>> CONTAINER A: DEFAULT INSECURE (ROOT USER, FULL PRIVILEGES) <<<`);
  const insecureContainer = new HardenedContainerSimulator('insecure-app', {
    user: 0,
    noNewPrivileges: false,
    capabilities: ['CAP_CHOWN', 'CAP_NET_RAW', 'CAP_SYS_ADMIN'],
    readOnlyRoot: false,
    tmpfsNoexec: false
  });

  const attack1A = insecureContainer.attemptPrivilegeEscalation();
  const attack2A = insecureContainer.attemptRawNetworkAccess();
  const attack3A = insecureContainer.attemptWriteWebShell();
  const attack4A = insecureContainer.attemptExecuteMalwareInTmp();

  // BENCHMARK 2: Hardened CIS-Benchmark Compliant Container
  console.log(`\n======================================================`);
  console.log(`>>> CONTAINER B: HARDENED CIS-BENCHMARK COMPLIANT <<<`);
  console.log(`======================================================`);
  const hardenedContainer = new HardenedContainerSimulator('hardened-app', {
    user: 10001,
    noNewPrivileges: true,
    capabilities: [], // --cap-drop=ALL
    readOnlyRoot: true,
    tmpfsNoexec: true
  });

  const attack1B = hardenedContainer.attemptPrivilegeEscalation();
  const attack2B = hardenedContainer.attemptRawNetworkAccess();
  const attack3B = hardenedContainer.attemptWriteWebShell();
  const attack4B = hardenedContainer.attemptExecuteMalwareInTmp();

  // PRINT SCORECARD
  console.log(`\n========================================================================================`);
  console.log(`📊 SECURITY HARDENING SCORECARD MATRIX`);
  console.log(`========================================================================================`);
  console.log(`Attack Vector                     | Default Insecure Container | Hardened Container (CIS)`);
  console.log(`----------------------------------|----------------------------|--------------------------`);
  console.log(`1. SUID Privilege Escalation      | ${attack1A ? '❌ COMPROMISED (Root)' : '🟢 BLOCKED'}    | ${attack1B ? '❌ COMPROMISED' : '🟢 BLOCKED (no-new-privileges)'}`);
  console.log(`2. Raw Network Packet Sniffing    | ${attack2A ? '❌ COMPROMISED (Raw Socket)' : '🟢 BLOCKED'}| ${attack2B ? '❌ COMPROMISED' : '🟢 BLOCKED (--cap-drop=ALL)'}`);
  console.log(`3. Web Shell Backdoor Injection   | ${attack3A ? '❌ COMPROMISED (Written)' : '🟢 BLOCKED'}   | ${attack3B ? '❌ COMPROMISED' : '🟢 BLOCKED (--read-only rootfs)'}`);
  console.log(`4. Tmpfs Malware Script Execution | ${attack4A ? '❌ COMPROMISED (Running)' : '🟢 BLOCKED'}   | ${attack4B ? '❌ COMPROMISED' : '🟢 BLOCKED (--tmpfs noexec)'}`);
  console.log(`========================================================================================\n`);

  console.log(`🎉 Container Security Hardening Simulator Lab Complete!`);
}

runLab();
