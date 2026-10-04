/**
 * Hands-on M01: OpenClaw Proactive Cron & Heartbeat Scheduler Simulator
 * Mengilustrasikan mekanisme internal heartbeat check, job scheduling,
 * evaluasi kondisi proaktif, dan dispatching notifikasi otomatis ke user.
 *
 * Jalankan: node cron_heartbeat_scheduler.js
 */

const fs = require('fs');
const path = require('path');

// ANSI Colors untuk output visual
const colors = {
  reset: '\x1b[0m',
  cyan: '\x1b[36m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  magenta: '\x1b[35m',
  red: '\x1b[31m',
  bold: '\x1b[1m'
};

class ProactiveHeartbeatScheduler {
  constructor(options = {}) {
    this.agentName = options.agentName || 'OpenClaw-Worker';
    this.heartbeatIntervalMs = options.heartbeatIntervalMs || 2000;
    this.jobs = [];
    this.heartbeatTasks = [];
    this.stateFile = path.join(__dirname, 'scheduler_state.json');
    this.state = this.loadState();
    this.activeTimers = [];
  }

  loadState() {
    try {
      if (fs.existsSync(this.stateFile)) {
        return JSON.parse(fs.readFileSync(this.stateFile, 'utf8'));
      }
    } catch (e) {
      console.warn(`[WARN] Gagal membaca state lama, reset state: ${e.message}`);
    }
    return {
      lastHeartbeat: null,
      executedJobCount: 0,
      dispatchedAlerts: []
    };
  }

  saveState() {
    try {
      fs.writeFileSync(this.stateFile, JSON.stringify(this.state, null, 2));
    } catch (e) {
      console.error(`[ERR] Gagal menyimpan state: ${e.message}`);
    }
  }

  // Daftarkan scheduled job (misal: daily summary, hourly backup)
  registerJob(name, intervalMs, handler) {
    this.jobs.push({
      name,
      intervalMs,
      handler,
      lastRun: 0,
      runCount: 0
    });
    console.log(`${colors.cyan}[JOB REGISTERED]${colors.reset} "${name}" - Interval: ${intervalMs}ms`);
  }

  // Daftarkan heartbeat task (pemeriksaan kondisi pasif / ambang batas)
  registerHeartbeatCheck(name, checkFn) {
    this.heartbeatTasks.push({
      name,
      checkFn
    });
    console.log(`${colors.magenta}[HEARTBEAT CHECK REGISTERED]${colors.reset} "${name}"`);
  }

  // Simulasi dispatch pesan proaktif ke user melalui kanal
  dispatchNotification(channel, recipient, message) {
    const timestamp = new Date().toISOString().replace('T', ' ').substring(0, 19);
    console.log(`\n${colors.green}>>> [DISPATCH PROAKTIF ${channel.toUpperCase()}] ${timestamp}${colors.reset}`);
    console.log(`    Penerima : ${recipient}`);
    console.log(`    Pesan    : ${message}\n`);

    this.state.dispatchedAlerts.push({
      timestamp,
      channel,
      recipient,
      message
    });
    this.saveState();
  }

  // Siklus Heartbeat
  async executeHeartbeat() {
    const now = Date.now();
    this.state.lastHeartbeat = now;
    console.log(`\n${colors.yellow}[HEARTBEAT TICK]${colors.reset} Memeriksa ${this.heartbeatTasks.length} status sistem pada ${new Date(now).toLocaleTimeString()}...`);

    for (const task of this.heartbeatTasks) {
      try {
        const result = await task.checkFn();
        if (result && result.shouldAlert) {
          console.log(`  ${colors.red}! Kondisi kritis terdeteksi oleh: ${task.name}${colors.reset}`);
          this.dispatchNotification(
            result.channel || 'telegram',
            result.recipient || '@devops_lead',
            result.alertMessage
          );
        } else {
          console.log(`  [OK] ${task.name}: Normal (${result ? result.statusMessage : 'All clear'})`);
        }
      } catch (err) {
        console.error(`  [ERROR] Heartbeat task "${task.name}" gagal:`, err.message);
      }
    }
  }

  // Siklus Scheduler (Job Runner)
  async evaluateScheduledJobs() {
    const now = Date.now();
    for (const job of this.jobs) {
      if (now - job.lastRun >= job.intervalMs) {
        job.lastRun = now;
        job.runCount++;
        this.state.executedJobCount++;
        console.log(`\n${colors.cyan}[JOB EXECUTION] Menjalankan: "${job.name}" (Run #${job.runCount})${colors.reset}`);
        try {
          await job.handler(this);
        } catch (err) {
          console.error(`[JOB FAIL] Job "${job.name}" error:`, err.message);
        }
        this.saveState();
      }
    }
  }

  start() {
    console.log(`\n${colors.bold}${colors.green}=== Memulai Proactive Engine ${this.agentName} ===${colors.reset}`);
    
    // Heartbeat runner
    const heartbeatTimer = setInterval(() => {
      this.executeHeartbeat();
    }, this.heartbeatIntervalMs);
    this.activeTimers.push(heartbeatTimer);

    // Job scheduler runner (cek tiap 1 detik)
    const jobTimer = setInterval(() => {
      this.evaluateScheduledJobs();
    }, 1000);
    this.activeTimers.push(jobTimer);
  }

  stop() {
    this.activeTimers.forEach(timer => clearInterval(timer));
    this.activeTimers = [];
    console.log(`\n${colors.yellow}=== Engine ${this.agentName} Dihentikan ===${colors.reset}`);
  }
}

// ==========================================
// SIMULASI PRAKTIK REAL-WORLD
// ==========================================
async function runSimulation() {
  const scheduler = new ProactiveHeartbeatScheduler({
    agentName: 'OpenClaw-Daemon-Node1',
    heartbeatIntervalMs: 2500 // Cek vitals tiap 2.5s dalam lab
  });

  // 1. Daftarkan Job Cron Terjadwal: "Morning Daily Briefing" (interval disimulasi 5 detik)
  scheduler.registerJob('Daily Morning Briefing', 5000, async (engine) => {
    const summary = 'Halo Tuan! Berikut ringkasan hari ini: 3 meeting terjadwal, cuaca Jakarta 28C cerah berawan, PR #42 membutuhkan review Anda.';
    engine.dispatchNotification('telegram', '@ceo_user', summary);
  });

  // 2. Daftarkan Heartbeat Check 1: Pemantauan Penggunaan Disk VPS
  let mockDiskUsagePercent = 75;
  scheduler.registerHeartbeatCheck('Disk Storage Watchdog', async () => {
    // Disk bertambah pada simulasi
    mockDiskUsagePercent += 10;
    if (mockDiskUsagePercent >= 90) {
      return {
        shouldAlert: true,
        channel: 'telegram',
        recipient: '@admin',
        alertMessage: `[KRITIS] Penyimpanan VPS mendekati kapasitas penuh: ${mockDiskUsagePercent}% terpakai! Segera bersihkan log / docker cache.`
      };
    }
    return {
      shouldAlert: false,
      statusMessage: `Disk terpakai: ${mockDiskUsagePercent}% (Batas aman < 90%)`
    };
  });

  // 3. Daftarkan Heartbeat Check 2: SLA API Service Monitoring
  let errorCountCounter = 0;
  scheduler.registerHeartbeatCheck('External Gateway API Ping', async () => {
    errorCountCounter++;
    if (errorCountCounter === 2) {
      return {
        shouldAlert: true,
        channel: 'discord',
        recipient: '#incident-channel',
        alertMessage: '[WARNING] Payment Gateway API mengembalikan HTTP 504 Gateway Timeout berturut-turut.'
      };
    }
    return {
      shouldAlert: false,
      statusMessage: 'Semua upstream endpoint 200 OK'
    };
  });

  // Jalankan simulator
  scheduler.start();

  // Berhenti otomatis setelah 8.5 detik agar demonstrasi selesai dan dapat diverifikasi
  setTimeout(() => {
    scheduler.stop();
    console.log(`${colors.green}[VERIFIKASI SUKSES] Simulasi Heartbeat & Cron Scheduler selesai.${colors.reset}`);
    
    // Tampilkan ringkasan state yang tersimpan
    const finalState = scheduler.loadState();
    console.log('\n--- State Akhir (scheduler_state.json) ---');
    console.log(`Total Job Berjalan : ${finalState.executedJobCount}`);
    console.log(`Total Notifikasi   : ${finalState.dispatchedAlerts.length}`);
    console.log('-------------------------------------------\n');

    // Cleanup state file
    try {
      if (fs.existsSync(scheduler.stateFile)) {
        fs.unlinkSync(scheduler.stateFile);
      }
    } catch (_) {}

    process.exit(0);
  }, 8500);
}

runSimulation();
