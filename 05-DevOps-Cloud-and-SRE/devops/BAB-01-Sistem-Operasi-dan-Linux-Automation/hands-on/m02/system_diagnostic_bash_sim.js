/**
 * Hands-on M02: DevOps Linux System Diagnostic & Systemd Service Simulator
 * Mengilustrasikan konsep:
 * 1. USE Method System Diagnostic (CPU Load, Memory, Disk, Sockets)
 * 2. Systemd Service Unit Lifecycle & Auto-Restart Watchdog
 * 3. Defensive Shell Scripting (Bash Strict Mode: set -euo pipefail)
 *
 * Jalankan: node system_diagnostic_bash_sim.js
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

// ==========================================
// 1. SYSTEM DIAGNOSTIC (USE METHOD SIMULATOR)
// ==========================================
class SystemDiagnosticTool {
  constructor(hostname = 'prod-api-cluster-01') {
    this.hostname = hostname;
  }

  collectMetrics() {
    // Simulasi pembacaan dari /proc/loadavg, /proc/meminfo, dan /proc/diskstats
    const cpuLoad1m = (2.8 + Math.random() * 2.5).toFixed(2);
    const cpuCores = 4;
    const totalMemMb = 4096;
    const usedMemMb = Math.floor(3100 + Math.random() * 600);
    const freeMemMb = totalMemMb - usedMemMb;
    const diskTotalGb = 100;
    const diskUsedGb = 82; // 82% terpakai

    const topProcesses = [
      { pid: 1420, user: 'node', cpuPct: 68.4, memPct: 24.1, cmd: 'node /opt/api/server.js' },
      { pid: 981, user: 'postgres', cpuPct: 18.2, memPct: 35.0, cmd: 'postgres: writer process' },
      { pid: 612, user: 'nginx', cpuPct: 4.5, memPct: 3.2, cmd: 'nginx: worker process' }
    ];

    const activeSockets = [
      { proto: 'tcp', state: 'LISTEN', local: '0.0.0.0:80', process: 'nginx (PID 611)' },
      { proto: 'tcp', state: 'LISTEN', local: '127.0.0.1:3000', process: 'node (PID 1420)' },
      { proto: 'tcp', state: 'LISTEN', local: '127.0.0.1:5432', process: 'postgres (PID 980)' }
    ];

    return {
      hostname: this.hostname,
      cpu: { load1m: parseFloat(cpuLoad1m), cores: cpuCores, isSaturated: parseFloat(cpuLoad1m) > cpuCores },
      memory: { totalMb: totalMemMb, usedMb: usedMemMb, freeMb: freeMemMb, usedPct: ((usedMemMb / totalMemMb) * 100).toFixed(1) },
      disk: { totalGb: diskTotalGb, usedGb: diskUsedGb, usedPct: ((diskUsedGb / diskTotalGb) * 100).toFixed(1) },
      topProcesses,
      activeSockets
    };
  }

  generateTriageReport() {
    const data = this.collectMetrics();
    console.log(`\n${colors.bold}${colors.cyan}=== SYSTEM DIAGNOSTIC HEALTH REPORT (USE METHOD) ===${colors.reset}`);
    console.log(`Host: ${data.hostname} | Waktu: ${new Date().toISOString()}`);
    console.log('----------------------------------------------------');
    
    // CPU Check
    const cpuStatus = data.cpu.isSaturated ? `${colors.red}[WARNING SATURATED]` : `${colors.green}[OK]`;
    console.log(`CPU Load (1m) : ${data.cpu.load1m} / ${data.cpu.cores} Cores ${cpuStatus}${colors.reset}`);

    // Memory Check
    const memStatus = data.memory.usedPct > 85 ? `${colors.yellow}[HIGH USAGE]` : `${colors.green}[OK]`;
    console.log(`Memory Usage  : ${data.memory.usedMb}MB / ${data.memory.totalMb}MB (${data.memory.usedPct}%) ${memStatus}${colors.reset}`);

    // Disk Check
    const diskStatus = data.disk.usedPct > 80 ? `${colors.yellow}[DISK WARNING]` : `${colors.green}[OK]`;
    console.log(`Disk Storage  : ${data.disk.usedGb}GB / ${data.disk.totalGb}GB (${data.disk.usedPct}%) ${diskStatus}${colors.reset}`);

    console.log('\nTop 3 Resource-Heavy Processes:');
    data.topProcesses.forEach(p => {
      console.log(`  - PID ${p.pid} (${p.user}): CPU ${p.cpuPct}%, MEM ${p.memPct}% -> ${p.cmd}`);
    });

    console.log('\nActive Listening Sockets (ss -tulpn):');
    data.activeSockets.forEach(s => {
      console.log(`  - ${s.proto.toUpperCase()} ${s.local} [${s.state}] -> ${s.process}`);
    });
    console.log('----------------------------------------------------\n');
  }
}

// ==========================================
// 2. SYSTEMD SERVICE SUPERVISOR SIMULATOR
// ==========================================
class SystemdUnitSimulator {
  constructor(unitName, options = {}) {
    this.unitName = unitName;
    this.execStart = options.execStart || '/usr/bin/node /opt/api/server.js';
    this.restartPolicy = options.restartPolicy || 'on-failure';
    this.restartSec = options.restartSec || 1000;
    this.state = 'INACTIVE';
    this.pid = null;
    this.crashCount = 0;
  }

  start() {
    this.pid = Math.floor(2000 + Math.random() * 5000);
    this.state = 'ACTIVE (RUNNING)';
    console.log(`${colors.green}[SYSTEMD: ${this.unitName}] Service started successfully! PID: ${this.pid}${colors.reset}`);
  }

  simulateCrash(errorCode = 1) {
    console.log(`\n${colors.red}[SYSTEMD CRASH DETECTED] ${this.unitName} (PID ${this.pid}) terminated with exit code ${errorCode}${colors.reset}`);
    this.state = 'FAILED';
    this.pid = null;
    this.crashCount++;

    if (this.restartPolicy === 'on-failure' || this.restartPolicy === 'always') {
      console.log(`${colors.yellow}[SYSTEMD WATCHDOG] Restarting service in ${this.restartSec}ms according to Restart=${this.restartPolicy}...${colors.reset}`);
      setTimeout(() => {
        this.start();
      }, this.restartSec);
    }
  }

  status() {
    console.log(`* ${this.unitName} - Loaded: (/etc/systemd/system/${this.unitName}; enabled)`);
    console.log(`  Active: ${this.state} (PID: ${this.pid || 'none'})`);
    console.log(`  ExecStart: ${this.execStart}`);
    console.log(`  Restarts: ${this.crashCount}`);
  }
}

// ==========================================
// 3. DEFENSIVE BASH STRICT MODE SIMULATOR
// ==========================================
class BashStrictModeValidator {
  static evaluateScript(scriptName, lines, env = {}) {
    console.log(`\n${colors.bold}${colors.cyan}=== DEFENSIVE BASH PARSER: ${scriptName} ===${colors.reset}`);
    
    let hasStrictFlags = false;
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();

      if (line.includes('set -euo pipefail') || (line.includes('set -e') && line.includes('set -u'))) {
        hasStrictFlags = true;
        console.log(`  [OK Line ${i+1}] Ditemukan flag defensive: "${line}"`);
      }

      // Deteksi Unbound Variable ($DIR tanpa nilai)
      const unboundVarMatch = line.match(/\$([A-Z_]+)/);
      if (unboundVarMatch && !env[unboundVarMatch[1]]) {
        if (hasStrictFlags) {
          console.log(`  ${colors.red}[FAIL-FAST (set -u) Line ${i+1}] Error: Variabel $${unboundVarMatch[1]} belum didefinisikan! Eksekusi script dibatalkan seketika.${colors.reset}`);
          return { success: false, errorLine: i + 1, reason: `Unbound variable $${unboundVarMatch[1]}` };
        } else {
          console.log(`  ${colors.yellow}[WARNING (No set -u) Line ${i+1}] Variabel $${unboundVarMatch[1]} kosong! Script mengeksekusi dengan string kosong (Berbahaya!).${colors.reset}`);
        }
      }
    }

    console.log(`${colors.green}[PASSED] Script tervalidasi dengan aman.${colors.reset}`);
    return { success: true };
  }
}

// ==========================================
// TEST SCENARIOS
// ==========================================
async function runLab() {
  // 1. Uji Coba USE Method Diagnostic
  const diag = new SystemDiagnosticTool('prod-ecommerce-gw01');
  diag.generateTriageReport();

  // 2. Uji Coba Systemd Service Manager
  console.log('--- SYSTEMD SERVICE MANAGER TEST ---');
  const paymentService = new SystemdUnitSimulator('payment-gateway.service', {
    execStart: '/usr/bin/node /opt/payment/index.js',
    restartPolicy: 'on-failure',
    restartSec: 800
  });

  paymentService.start();
  paymentService.status();

  // Picu simulasi crash
  paymentService.simulateCrash(137);

  // Tunggu sejenak agar watchdog me-restart service
  await new Promise(r => setTimeout(r, 1200));
  paymentService.status();

  // 3. Uji Coba Defensive Bash Script
  console.log('\n--- BASH DEFENSIVE SCRIPT VALIDATION ---');
  const safeScript = [
    '#!/usr/bin/env bash',
    'set -euo pipefail',
    'readonly APP_DIR="/var/www/app"',
    'cd "$APP_DIR"',
    'npm test'
  ];
  BashStrictModeValidator.evaluateScript('deploy_safe.sh', safeScript, { APP_DIR: '/var/www/app' });

  const dangerousScript = [
    '#!/usr/bin/env bash',
    'set -euo pipefail',
    'rm -rf "$TARGET_CACHE_DIR/"',
    'echo "Done"'
  ];
  // TARGET_CACHE_DIR tidak ada di env -> harus dicegah oleh set -u!
  BashStrictModeValidator.evaluateScript('cleanup_dangerous.sh', dangerousScript, {});

  console.log(`\n${colors.bold}${colors.green}=== SEMUA LAB DIAGNOSTIK & AUTOMATION SELESAI DENGAN SUKSES ===${colors.reset}`);
}

runLab();
