/**
 * Hands-on M01: Linux Kernel Process Lifecycle, Signals, & Zombie Reaper Simulator
 * Mengilustrasikan konsep internal kernel Linux: Process Table, Fork/Exec,
 * Sinyal (SIGTERM vs SIGKILL), deteksi Zombie state, dan Zombie Reaping.
 *
 * Jalankan: node linux_process_manager.js
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

class SimulatedLinuxKernel {
  constructor(maxPids = 100) {
    this.maxPids = maxPids;
    this.nextPid = 1;
    this.processTable = new Map();

    // Inisialisasi System Init Process (PID 1 - systemd)
    this.spawnInitProcess();
  }

  spawnInitProcess() {
    const initProc = {
      pid: 1,
      ppid: 0,
      name: 'systemd (init)',
      state: 'S', // Interruptible Sleep (Waiting)
      memoryMb: 18,
      exitCode: null,
      signalHandlers: {
        SIGTERM: () => console.log('  [PID 1] Menolak SIGTERM (Init process tidak boleh mati sembarangan!)'),
        SIGCHLD: () => this.reapOrphans()
      }
    };
    this.processTable.set(1, initProc);
    this.nextPid = 2;
  }

  // Syscall fork()
  fork(parentPid, programName, memoryMb = 32) {
    if (this.processTable.size >= this.maxPids) {
      throw new Error(`ENOMEM: Kernel process table penuh! Batas max PID (${this.maxPids}) tercapai.`);
    }

    const parent = this.processTable.get(parentPid);
    if (!parent) {
      throw new Error(`ESRCH: Parent process dengan PID ${parentPid} tidak ditemukan.`);
    }

    const childPid = this.nextPid++;
    const childProc = {
      pid: childPid,
      ppid: parentPid,
      name: programName,
      state: 'R', // Running
      memoryMb,
      exitCode: null,
      signalHandlers: {
        SIGTERM: (proc) => {
          console.log(`  [PID ${proc.pid} - ${proc.name}] Menerima SIGTERM: Menutup koneksi & flush buffer...`);
          this.exit(proc.pid, 0);
        }
      }
    };

    this.processTable.set(childPid, childProc);
    console.log(`${colors.cyan}[SYSCALL FORK]${colors.reset} Parent (PID ${parentPid}) -> Child baru: PID ${childPid} (${programName})`);
    return childPid;
  }

  // Syscall exit()
  exit(pid, exitCode = 0) {
    const proc = this.processTable.get(pid);
    if (!proc) return false;

    // Memori RAM dilepas seketika
    proc.memoryMb = 0;
    proc.exitCode = exitCode;

    // Jika parent masih ada tetapi belum waitpid, proses berubah jadi ZOMBIE
    proc.state = 'Z';
    console.log(`${colors.yellow}[PROCESS EXIT]${colors.reset} PID ${pid} (${proc.name}) selesai (Exit Code: ${exitCode}). Berubah menjadi state: ${colors.red}[ZOMBIE]${colors.reset}`);

    // Beri sinyal SIGCHLD ke parent
    const parent = this.processTable.get(proc.ppid);
    if (parent && parent.signalHandlers.SIGCHLD) {
      parent.signalHandlers.SIGCHLD();
    }
    return true;
  }

  // Syscall waitpid() - Reaping zombie process
  waitpid(parentPid, childPid) {
    const child = this.processTable.get(childPid);
    if (!child) return false;

    if (child.ppid !== parentPid && parentPid !== 1) {
      throw new Error(`ECHILD: Proses ${childPid} bukan anak dari PID ${parentPid}`);
    }

    if (child.state === 'Z') {
      this.processTable.delete(childPid);
      console.log(`${colors.green}[ZOMBIE REAPED]${colors.reset} Parent PID ${parentPid} membaca exit status (${child.exitCode}). PID ${childPid} dihapus dari kernel process table.`);
      return true;
    }
    return false;
  }

  // Syscall kill(pid, signal)
  kill(pid, signal) {
    const proc = this.processTable.get(pid);
    if (!proc) {
      console.log(`${colors.red}[KILL FAIL] PID ${pid} tidak ditemukan.${colors.reset}`);
      return false;
    }

    console.log(`\n${colors.magenta}[SEND SIGNAL] Mengirim sinyal ${signal} ke PID ${pid} (${proc.name})...${colors.reset}`);

    if (signal === 'SIGKILL') {
      // SIGKILL (9) tidak dapat ditangkap atau diabaikan oleh proses!
      console.log(`  ${colors.red}[KERNEL ENFORCED] Sinyal SIGKILL (9) dieksekusi paksa oleh kernel!${colors.reset}`);
      this.exit(pid, 137);
      return true;
    }

    if (signal === 'SIGTERM') {
      // SIGTERM (15) dapat ditangkap untuk graceful shutdown
      if (proc.signalHandlers && proc.signalHandlers.SIGTERM) {
        proc.signalHandlers.SIGTERM(proc);
      } else {
        // Default action: Terminate
        this.exit(pid, 143);
      }
      return true;
    }

    return false;
  }

  // Reaping orphan zombies oleh init (PID 1)
  reapOrphans() {
    for (const [pid, proc] of this.processTable.entries()) {
      if (proc.state === 'Z' && (!this.processTable.has(proc.ppid) || proc.ppid === 1)) {
        this.processTable.delete(pid);
        console.log(`  ${colors.green}[INIT REAPER (PID 1)] Berhasil membersihkan orphan zombie PID ${pid}.${colors.reset}`);
      }
    }
  }

  // Tampilkan tabel proses ala command `ps aux`
  printProcessTable() {
    console.log(`\n${colors.bold}=== SIMULATED LINUX KERNEL PROCESS TABLE (ps aux) ===${colors.reset}`);
    console.log('PID\tPPID\tSTAT\tMEM(MB)\tCOMMAND');
    console.log('----------------------------------------------------');
    for (const [pid, proc] of this.processTable.entries()) {
      let statColor = colors.green;
      if (proc.state === 'Z') statColor = colors.red;
      else if (proc.state === 'S') statColor = colors.cyan;

      console.log(`${proc.pid}\t${proc.ppid}\t${statColor}${proc.state}${colors.reset}\t${proc.memoryMb}\t${proc.name}`);
    }
    console.log('----------------------------------------------------\n');
  }
}

// ==========================================
// TEST SCENARIOS
// ==========================================
async function runLab() {
  console.log(`${colors.bold}${colors.cyan}=== DEVOPS LAB: LINUX PROCESS & SIGNAL MANAGEMENT ===${colors.reset}\n`);

  const kernel = new SimulatedLinuxKernel(50);
  kernel.printProcessTable();

  // 1. Fork aplikasi web server Nginx dari PID 1
  console.log('--- 1. SPAWN PROCESS (FORK) ---');
  const nginxMasterPid = kernel.fork(1, 'nginx: master process', 48);
  const nginxWorker1 = kernel.fork(nginxMasterPid, 'nginx: worker process', 24);
  const nginxWorker2 = kernel.fork(nginxMasterPid, 'nginx: worker process', 24);

  // Fork aplikasi backend Node.js
  const nodeAppPid = kernel.fork(1, 'node /app/server.js', 128);
  kernel.printProcessTable();

  // 2. Simulasi Sinyal Graceful Shutdown (SIGTERM)
  console.log('--- 2. PENGUJIAN SINYAL SIGTERM (GRACEFUL SHUTDOWN) ---');
  kernel.kill(nodeAppPid, 'SIGTERM');
  kernel.printProcessTable();

  // 3. Simulasi Terjadinya Zombie Process
  console.log('--- 3. SIMULASI ZOMBIE PROCESS ---');
  console.log('Nginx Worker 1 tiba-tiba exit, tetapi Nginx Master sibuk dan belum memanggil waitpid()...');
  kernel.exit(nginxWorker1, 0);
  kernel.printProcessTable();

  // 4. Parent Melakukan Reaping (waitpid)
  console.log('--- 4. ZOMBIE REAPING VIA WAITPID() ---');
  kernel.waitpid(nginxMasterPid, nginxWorker1);
  kernel.printProcessTable();

  // 5. Simulasi Forced Kill (SIGKILL - kill -9)
  console.log('--- 5. PENGUJIAN SINYAL SIGKILL (KILL -9) ---');
  kernel.kill(nginxWorker2, 'SIGKILL');
  kernel.waitpid(nginxMasterPid, nginxWorker2);
  kernel.printProcessTable();

  console.log(`${colors.bold}${colors.green}=== SEMUA SIMULASI SIKLUS PROSES KERNEL SELESAI DENGAN SUKSES ===${colors.reset}`);
}

runLab();
