/**
 * Hands-on M01: OpenClaw Permission Model, Shell Sandboxing, & Human-in-the-Loop Simulator
 * Mengilustrasikan interceptor kebijakan perintah, alur persetujuan manusia (HITL),
 * dan eksekusi terisolasi dalam sandbox.
 *
 * Jalankan: node permission_sandbox_sim.js
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

class SecurityInterceptor {
  constructor() {
    this.hardDenylist = [
      /rm\s+-rf\s+(\/|\*|~\/)/i,
      /mkfs/i,
      /dd\s+if=/i,
      /:(){ :|:& };:/i,
      />\s*\/dev\/sd[a-z]/i,
      /chmod\s+-R\s+777\s+\//i
    ];

    this.hitlApprovalList = [
      /git\s+(push|reset\s+--hard)/i,
      /docker\s+(run|rm|kill|stop)/i,
      /pm2\s+(restart|delete|stop)/i,
      /systemctl\s+(restart|stop)/i,
      /npm\s+publish/i,
      /drop\s+table/i
    ];
  }

  evaluate(command) {
    const trimmed = command.trim();

    // 1. Cek Hard Denylist
    for (const pattern of this.hardDenylist) {
      if (pattern.test(trimmed)) {
        return {
          tier: 'HARD_BLOCK',
          allowed: false,
          reason: 'Perintah berbahaya terdeteksi dalam denylist destruktif sistem'
        };
      }
    }

    // 2. Cek apakah butuh persetujuan manusia (HITL)
    for (const pattern of this.hitlApprovalList) {
      if (pattern.test(trimmed)) {
        return {
          tier: 'REQUIRES_APPROVAL',
          allowed: false,
          needsHumanApproval: true,
          reason: 'Perintah berpotensi mengubah status sistem atau menghapus data'
        };
      }
    }

    // 3. Default: Safe (Read-only atau dev tools standar)
    return {
      tier: 'AUTO_ALLOW',
      allowed: true,
      reason: 'Perintah tergolong aman (read-only atau low-risk dev tool)'
    };
  }
}

class SandboxExecutor {
  constructor(timeoutMs = 3000) {
    this.timeoutMs = timeoutMs;
  }

  async executeInSandbox(command, executionContext = {}) {
    console.log(`  ${colors.cyan}[SANDBOX RUNNER] Menyiapkan lingkungan container terisolasi...${colors.reset}`);
    console.log(`    - User: agent-sandbox (UID 1000, unprivileged)`);
    console.log(`    - Rootfs: read-only, Vol Mount: /workspace (bounded)`);
    console.log(`    - Timeout: ${this.timeoutMs}ms, Max Memory: 512MB`);

    // Simulasi eksekusi perintah di sandbox
    await new Promise(r => setTimeout(r, 400));

    return {
      success: true,
      exitCode: 0,
      stdout: `[SANDBOX_STDOUT] Perintah "${command}" berhasil dieksekusi tanpa error.`,
      executionTimeMs: 420
    };
  }
}

class HITLApprovalManager {
  constructor() {
    this.pendingRequests = new Map();
  }

  // Membuat request tiket approval
  createApprovalTicket(command, reason, timeoutMs = 2000) {
    const ticketId = 'hitl_' + Math.random().toString(36).substring(2, 9);
    
    const promise = new Promise((resolve) => {
      const timer = setTimeout(() => {
        if (this.pendingRequests.has(ticketId)) {
          console.log(`  ${colors.red}[HITL TIMEOUT] Tiket ${ticketId} kedaluwarsa setelah ${timeoutMs}ms tanpa respons!${colors.reset}`);
          this.pendingRequests.delete(ticketId);
          resolve({ approved: false, reason: 'Human Approval Timeout (Auto-Rejected)' });
        }
      }, timeoutMs);

      this.pendingRequests.set(ticketId, { resolve, timer, command });
    });

    return { ticketId, promise };
  }

  // Menanggapi tiket approval (disimulasikan dari klik tombol di Telegram)
  respond(ticketId, isApproved, approvedBy = '@system_admin') {
    if (!this.pendingRequests.has(ticketId)) {
      return false;
    }
    const { resolve, timer, command } = this.pendingRequests.get(ticketId);
    clearTimeout(timer);
    this.pendingRequests.delete(ticketId);

    console.log(`  ${colors.green}[HITL DISPATCH] Pengguna ${approvedBy} ${isApproved ? 'MENYETUJUI' : 'MENOLAK'} perintah: "${command}"${colors.reset}`);
    resolve({ approved: isApproved, approvedBy, reason: isApproved ? 'Approved by operator' : 'Rejected by operator' });
    return true;
  }
}

// ==========================================
// TEST SCENARIO
// ==========================================
async function runLab() {
  console.log(`${colors.bold}${colors.cyan}=== OPENCLAW SECURITY INTERCEPTOR & HITL SANDBOX LAB ===${colors.reset}\n`);

  const interceptor = new SecurityInterceptor();
  const sandbox = new SandboxExecutor(3000);
  const hitlManager = new HITLApprovalManager();

  // Test Case 1: Perintah Safe / Read-Only (Auto-Allow)
  console.log('--- TEST CASE 1: Perintah Read-Only (`git status`) ---');
  const cmd1 = 'git status';
  const eval1 = interceptor.evaluate(cmd1);
  console.log(`Evaluasi Kebijakan: ${eval1.tier} (${eval1.reason})`);
  if (eval1.allowed) {
    const result = await sandbox.executeInSandbox(cmd1);
    console.log(`Hasil: [Exit ${result.exitCode}] ${result.stdout}\n`);
  }

  // Test Case 2: Perintah Destruktif Ekstrem (Hard Block)
  console.log('--- TEST CASE 2: Perintah Berbahaya (`rm -rf /`) ---');
  const cmd2 = 'rm -rf /';
  const eval2 = interceptor.evaluate(cmd2);
  console.log(`Evaluasi Kebijakan: ${colors.red}${eval2.tier}${colors.reset} (${eval2.reason})`);
  if (!eval2.allowed && !eval2.needsHumanApproval) {
    console.log(`${colors.red}[ACTION BLOCKED] Perintah dibatalkan seketika tanpa dieksekusi.${colors.reset}\n`);
  }

  // Test Case 3: Perintah Berisiko dengan HITL Approval (User Menyetujui)
  console.log('--- TEST CASE 3: Perintah Kritis dengan HITL Disetujui (`pm2 restart payment-api`) ---');
  const cmd3 = 'pm2 restart payment-api';
  const eval3 = interceptor.evaluate(cmd3);
  console.log(`Evaluasi Kebijakan: ${colors.yellow}${eval3.tier}${colors.reset} (${eval3.reason})`);
  
  if (eval3.needsHumanApproval) {
    console.log(`  -> Mengirim notifikasi approval prompt ke Telegram Admin...`);
    const { ticketId, promise } = hitlManager.createApprovalTicket(cmd3, eval3.reason, 2000);
    
    // Simulasikan admin menekan tombol "APPROVE" di Telegram setelah 500ms
    setTimeout(() => {
      hitlManager.respond(ticketId, true, '@lead_devops');
    }, 500);

    const hitlResult = await promise;
    if (hitlResult.approved) {
      console.log(`  -> Otorisasi diterima. Melanjutkan eksekusi ke sandbox...`);
      const result = await sandbox.executeInSandbox(cmd3);
      console.log(`Hasil: [Exit ${result.exitCode}] ${result.stdout}\n`);
    }
  }

  // Test Case 4: Perintah Kritis yang Timeout / Ditolak
  console.log('--- TEST CASE 4: Perintah Kritis dengan HITL Timeout / Diabaikan ---');
  const cmd4 = 'git reset --hard origin/main';
  const eval4 = interceptor.evaluate(cmd4);
  console.log(`Evaluasi Kebijakan: ${colors.yellow}${eval4.tier}${colors.reset}`);
  
  if (eval4.needsHumanApproval) {
    console.log(`  -> Menunggu persetujuan (timeout diset 1000ms)...`);
    const { ticketId, promise } = hitlManager.createApprovalTicket(cmd4, eval4.reason, 1000);

    // Operator tidak merespons (dibiarkan timeout)
    const hitlResult = await promise;
    if (!hitlResult.approved) {
      console.log(`${colors.red}[EKSEKUSI DIGAGALKAN] Status: ${hitlResult.reason}${colors.reset}\n`);
    }
  }

  console.log(`${colors.bold}${colors.green}=== SEMUA SKENARIO PENGUJIAN KEAMANAN SELESAI DENGAN SUKSES ===${colors.reset}`);
}

runLab();
