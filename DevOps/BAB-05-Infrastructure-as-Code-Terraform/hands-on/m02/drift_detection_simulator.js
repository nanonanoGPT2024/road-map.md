/**
 * Hands-on M02: Terraform Remote State Locking & Configuration Drift Detection Simulator
 * Mengilustrasikan konsep:
 * 1. Distributed Mutex State Locking (DynamoDB LockID)
 * 2. Deteksi Configuration Drift (Perubahan manual di luar Terraform)
 * 3. Rekonsiliasi Otomatis (Reverting Cloud State kembali ke Git HCL)
 *
 * Jalankan: node drift_detection_simulator.js
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
// 1. DISTRIBUTED STATE LOCKING (DYNAMODB SIMULATOR)
// ==========================================
class DistributedStateBackend {
  constructor(bucketName) {
    this.bucketName = bucketName;
    this.activeLock = null; // { lockId, who, acquiredAt }
    this.stateData = null;
  }

  acquireLock(operatorName) {
    if (this.activeLock) {
      const err = new Error(`Error acquiring the state lock: ConditionalCheckFailedException.\n` +
        `Lock Info:\n  ID: ${this.activeLock.lockId}\n  Owner: ${this.activeLock.who}\n  Acquired: ${this.activeLock.acquiredAt}`);
      err.code = 'STATE_LOCKED';
      throw err;
    }

    const lockId = 'lock_' + Math.random().toString(36).substring(2, 9);
    this.activeLock = {
      lockId,
      who: operatorName,
      acquiredAt: new Date().toISOString()
    };
    console.log(`  ${colors.green}[STATE LOCK ACQUIRED]${colors.reset} Operator "${operatorName}" berhasil mengunci state (LockID: ${lockId})`);
    return lockId;
  }

  releaseLock(lockId) {
    if (!this.activeLock || this.activeLock.lockId !== lockId) {
      console.log(`  ${colors.red}[LOCK RELEASE FAILED] Invalid LockID: ${lockId}${colors.reset}`);
      return false;
    }
    const owner = this.activeLock.who;
    this.activeLock = null;
    console.log(`  ${colors.cyan}[STATE LOCK RELEASED]${colors.reset} Kunci state dilepas oleh "${owner}"`);
    return true;
  }
}

// ==========================================
// 2. CONFIGURATION DRIFT DETECTION ENGINE
// ==========================================
class CloudDriftDetector {
  constructor(backend) {
    this.backend = backend;
    // Kondisi live di cloud saat ini
    this.liveCloudResources = new Map();
    // Kode deklaratif HCL di Git repository
    this.gitHclConfig = new Map();
  }

  registerResource(key, attributes) {
    this.gitHclConfig.set(key, JSON.parse(JSON.stringify(attributes)));
    this.liveCloudResources.set(key, JSON.parse(JSON.stringify(attributes)));
  }

  // Simulasi perubahan nakal via Cloud Console (ClickOps)
  simulateManualClickOpsChange(key, modifiedAttribute, newValue) {
    console.log(`\n${colors.red}[OUT-OF-BAND CHANGE (CLICKOPS)]${colors.reset} Sysadmin mengubah ${key}.${modifiedAttribute} secara manual di AWS Console menjadi: "${newValue}"`);
    const live = this.liveCloudResources.get(key);
    if (live) {
      live[modifiedAttribute] = newValue;
    }
  }

  // Pindai Drift (Membandingkan Git HCL vs Live Cloud)
  detectDrift() {
    console.log(`\n${colors.bold}${colors.cyan}=== SCANNING FOR CONFIGURATION DRIFT ===${colors.reset}`);
    const drifts = [];

    for (const [key, gitAttrs] of this.gitHclConfig.entries()) {
      const liveAttrs = this.liveCloudResources.get(key);
      if (!liveAttrs) {
        drifts.push({ key, type: 'MISSING_IN_CLOUD' });
        continue;
      }

      for (const prop of Object.keys(gitAttrs)) {
        if (gitAttrs[prop] !== liveAttrs[prop]) {
          drifts.push({
            key,
            property: prop,
            gitExpected: gitAttrs[prop],
            cloudActual: liveAttrs[prop]
          });
        }
      }
    }

    if (drifts.length === 0) {
      console.log(`${colors.green}[NO DRIFT] Infrastruktur cloud selaras 100% dengan kode Git HCL!${colors.reset}\n`);
      return false;
    }

    console.log(`${colors.yellow}[DRIFT DETECTED] Ditemukan ${drifts.length} perbedaan antara Git dan Cloud:${colors.reset}`);
    drifts.forEach(d => {
      console.log(`  * Resource : ${d.key}`);
      console.log(`    Properti : ${d.property}`);
      console.log(`    Di Git   : ${colors.green}${d.gitExpected}${colors.reset}`);
      console.log(`    Di Cloud : ${colors.red}${d.cloudActual}${colors.reset}`);
    });
    console.log('');
    return drifts;
  }

  // Rekonsiliasi Otomatis (Re-apply Git HCL)
  reconcile(drifts) {
    console.log(`${colors.bold}${colors.magenta}=== RECONCILING INFRASTRUCTURE BACK TO GIT TRUTH ===${colors.reset}`);
    for (const d of drifts) {
      const live = this.liveCloudResources.get(d.key);
      live[d.property] = d.gitExpected;
      console.log(`  ${colors.green}[REVERTED]${colors.reset} Mengembalikan ${d.key}.${d.property} ke nilai Git: "${d.gitExpected}"`);
    }
    console.log(`${colors.green}[RECONCILIATION COMPLETE] Cloud telah kembali sesuai spesifikasi Git!${colors.reset}\n`);
  }
}

// ==========================================
// TEST SCENARIOS
// ==========================================
async function runLab() {
  console.log(`${colors.bold}${colors.cyan}=== DEVOPS LAB: TERRAFORM LOCKING & DRIFT DETECTION ===${colors.reset}\n`);

  // 1. Uji Coba Distributed State Locking
  console.log('--- 1. UJI DISTRIBUTED STATE LOCKING (DYNAMODB MUTEX) ---');
  const backend = new DistributedStateBackend('corp-terraform-states-s3');

  // Engineer A mulai menjalankan apply
  console.log('Engineer A (Andi) menjalankan `terraform apply`...');
  const lockA = backend.acquireLock('Andi (DevOps)');

  // Engineer B (Budi) mencoba menjalankan apply bersamaan -> Harus gagal!
  console.log('\nEngineer B (Budi) serentak menjalankan `terraform apply`...');
  try {
    backend.acquireLock('Budi (SRE)');
  } catch (err) {
    console.log(`${colors.red}[RACE CONDITION PREVENTED]${colors.reset} Eksekusi Budi dibatalkan:\n${err.message}\n`);
  }

  // Engineer A selesai apply dan melepas lock
  console.log('Engineer A selesai.');
  backend.releaseLock(lockA);

  // Sekarang Budi dapat memperoleh lock dengan aman
  console.log('\nEngineer B mencoba kembali setelah kunci dilepas...');
  const lockB = backend.acquireLock('Budi (SRE)');
  backend.releaseLock(lockB);

  // 2. Uji Coba Configuration Drift Detection & Reconciliation
  console.log('\n--- 2. UJI COBA DRIFT DETECTION & AUTO-RECONCILIATION ---');
  const driftDetector = new CloudDriftDetector(backend);

  // Inisialisasi resource standar di Git & Cloud
  driftDetector.registerResource('aws_security_group.web_firewall', {
    port: 443,
    cidr: '0.0.0.0/0',
    description: 'Allow HTTPS traffic'
  });

  // Pengecekan drift saat awal (harus bersih)
  driftDetector.detectDrift();

  // Simulasikan insiden: Seseorang mengubah port 443 menjadi 8080 secara manual di AWS Console
  driftDetector.simulateManualClickOpsChange('aws_security_group.web_firewall', 'port', 8080);

  // Pipeline malam hari mendeteksi drift
  const drifts = driftDetector.detectDrift();

  // Rekonsiliasi kembali ke Git spec
  if (drifts) {
    driftDetector.reconcile(drifts);
  }

  // Pengecekan ulang pasca rekonsiliasi
  driftDetector.detectDrift();

  console.log(`${colors.bold}${colors.green}=== SEMUA PENGUJIAN LOCKING & DRIFT SELESAI DENGAN SUKSES ===${colors.reset}`);
}

runLab();
