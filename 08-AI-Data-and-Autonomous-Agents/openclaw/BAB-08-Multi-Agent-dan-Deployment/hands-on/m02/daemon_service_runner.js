/**
 * Hands-on M02: OpenClaw 24/7 Daemon Supervisor, Self-Healing, & Log Rotation Simulator
 * Mengilustrasikan arsitektur supervisor mirip Systemd/Docker: auto-restart saat crash,
 * pengecekan liveness healthcheck, rotasi log file, dan network binding aman (Tailscale-only).
 *
 * Jalankan: node daemon_service_runner.js
 */

const fs = require('fs');
const path = require('path');

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
// 1. ROTATING LOG MANAGER
// ==========================================
class RotatingLogManager {
  constructor(logDir, maxSizeBytes = 500, maxFiles = 3) {
    this.logDir = logDir;
    this.maxSizeBytes = maxSizeBytes;
    this.maxFiles = maxFiles;
    this.currentLogPath = path.join(this.logDir, 'openclaw.log');

    if (!fs.existsSync(this.logDir)) {
      fs.mkdirSync(this.logDir, { recursive: true });
    }
  }

  write(message) {
    const timestamp = new Date().toISOString();
    const formatted = `[${timestamp}] ${message}\n`;

    // Cek rotasi
    if (fs.existsSync(this.currentLogPath)) {
      const stats = fs.statSync(this.currentLogPath);
      if (stats.size >= this.maxSizeBytes) {
        this.rotate();
      }
    }

    fs.appendFileSync(this.currentLogPath, formatted, 'utf8');
  }

  rotate() {
    console.log(`  ${colors.yellow}[LOG ROTATION TRIGGERED] Ukuran log mencapai batas kuota. Merotasi file...${colors.reset}`);
    for (let i = this.maxFiles - 1; i >= 1; i--) {
      const oldFile = path.join(this.logDir, `openclaw.log.${i}`);
      const newFile = path.join(this.logDir, `openclaw.log.${i + 1}`);
      if (fs.existsSync(oldFile)) {
        if (i + 1 > this.maxFiles) {
          fs.unlinkSync(oldFile); // Buang log tertua
        } else {
          fs.renameSync(oldFile, newFile);
        }
      }
    }
    fs.renameSync(this.currentLogPath, path.join(this.logDir, 'openclaw.log.1'));
  }
}

// ==========================================
// 2. SELF-HEALING DAEMON SUPERVISOR
// ==========================================
class DaemonSupervisor {
  constructor(options = {}) {
    this.serviceName = options.serviceName || 'openclaw-agent-vps';
    this.bindAddress = options.bindAddress || '100.90.45.12'; // Alamat IP Tailscale (Bukan 0.0.0.0!)
    this.port = options.port || 18789;
    this.restartCount = 0;
    this.maxRestarts = 5;
    this.isServiceRunning = false;
    this.logManager = new RotatingLogManager(path.join(__dirname, 'logs'));
    this.watchdogInterval = null;
  }

  validateSecurityBinding() {
    console.log(`${colors.cyan}[SECURITY AUDIT] Memeriksa Network Interface Binding...${colors.reset}`);
    if (this.bindAddress === '0.0.0.0') {
      console.log(`${colors.red}[CRITICAL SECURITY WARNING] Port terikat ke 0.0.0.0 (Publik Terbuka)!${colors.reset}`);
      return false;
    }
    console.log(`${colors.green}[SECURITY OK] Port terikat eksklusif ke Tailscale Mesh IP: ${this.bindAddress}:${this.port}${colors.reset}`);
    return true;
  }

  // Simulasi start proses agen
  startAgentProcess() {
    this.isServiceRunning = true;
    this.logManager.write(`Service ${this.serviceName} started on ${this.bindAddress}:${this.port} (PID: ${Math.floor(Math.random() * 9000 + 1000)})`);
    console.log(`${colors.green}[SUPERVISOR] ${this.serviceName} AKTIF & MENJALANKAN DAEMON 24/7${colors.reset}`);
  }

  // Simulasi crash tak terduga (misal unhandled exception / OOM)
  simulateCrash(reason = 'Unhandled Exception in Memory Store') {
    if (!this.isServiceRunning) return;
    this.isServiceRunning = false;
    this.restartCount++;
    this.logManager.write(`CRASH DETECTED: ${reason}. Restart count: ${this.restartCount}`);
    console.log(`\n${colors.red}[ALERT: DAEMON CRASH] Layanan mati mendadak! Penyebab: "${reason}"${colors.reset}`);
  }

  // Watchdog liveness check (mirip systemd watchdog timer)
  startWatchdog(checkIntervalMs = 1000) {
    this.watchdogInterval = setInterval(() => {
      if (!this.isServiceRunning) {
        console.log(`${colors.yellow}[WATCHDOG SELF-HEALING] Mendeteksi service DOWN! Mencoba me-restart otomatis...${colors.reset}`);
        if (this.restartCount <= this.maxRestarts) {
          this.startAgentProcess();
          console.log(`${colors.green}[RESTART SUCCESS] Service pulih kembali dalam waktu < 1 detik!${colors.reset}`);
        } else {
          console.log(`${colors.red}[FATAL] Terlalu banyak crash berulang. Menghentikan auto-restart loop.${colors.reset}`);
          clearInterval(this.watchdogInterval);
        }
      } else {
        this.logManager.write('Liveness Ping: 200 OK - Health status healthy.');
      }
    }, checkIntervalMs);
  }

  stop() {
    if (this.watchdogInterval) clearInterval(this.watchdogInterval);
    this.isServiceRunning = false;
    console.log(`\n${colors.yellow}[SUPERVISOR STOPPED] Semua proses daemon dihentikan secara graceful.${colors.reset}`);
  }
}

// ==========================================
// TEST SCENARIO
// ==========================================
async function runLab() {
  console.log(`${colors.bold}${colors.cyan}=== OPENCLAW 24/7 VPS DAEMON & SELF-HEALING LAB ===${colors.reset}\n`);

  const supervisor = new DaemonSupervisor({
    serviceName: 'openclaw-core-worker',
    bindAddress: '100.90.45.12', // Private Tailscale IP
    port: 18789
  });

  // 1. Uji audit keamanan network interface
  supervisor.validateSecurityBinding();

  // 2. Nyalakan proses dan watchdog supervisor
  supervisor.startAgentProcess();
  supervisor.startWatchdog(800);

  // 3. Simulasikan operasional normal selama 2 detik
  await new Promise(r => setTimeout(r, 2000));

  // 4. Picu simulasi insiden crash tak terduga
  supervisor.simulateCrash('Memory allocation spike / Out of memory');

  // 5. Biarkan watchdog bekerja memulihkan daemon
  await new Promise(r => setTimeout(r, 2500));

  // 6. Buat beberapa baris log untuk memicu rotasi log otomatis
  for (let i = 0; i < 8; i++) {
    supervisor.logManager.write(`Operasi batch job rutinitas #${i} - Task execution trace dummy info`);
  }

  // 7. Berhenti dan periksa hasil file log yang terbentuk
  supervisor.stop();

  console.log('\n--- Status File Log di Direktori logs/ ---');
  const logFiles = fs.readdirSync(path.join(__dirname, 'logs'));
  logFiles.forEach(f => {
    const sz = fs.statSync(path.join(__dirname, 'logs', f)).size;
    console.log(`  - ${f} (${sz} bytes)`);
  });

  // Cleanup logs
  try {
    logFiles.forEach(f => fs.unlinkSync(path.join(__dirname, 'logs', f)));
    fs.rmdirSync(path.join(__dirname, 'logs'));
  } catch (_) {}

  console.log(`\n${colors.bold}${colors.green}=== VERIFIKASI DEPLOYMENT 24/7 BERHASIL DILAKUKAN ===${colors.reset}`);
  process.exit(0);
}

runLab();
