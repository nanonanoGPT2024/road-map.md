/**
 * Docker Volume Backup, Restore, & Integrity Verification Pipeline
 * Hands-on Lab: BAB 04 - Module 02
 * 
 * Demonstrates:
 * 1. Ephemeral Helper Container pattern for Volume Backup (`tar -czvf ...`).
 * 2. SHA256 Checksum generation for disaster recovery verification.
 * 3. Volume Destruction & Restore into a brand new Named Volume.
 * 4. Dangling Volume Garbage Collection & Pruning.
 */

const crypto = require('crypto');

class MockDockerStorageSystem {
  constructor() {
    this.volumes = new Map(); // volumeName -> Map(fileName, content)
    this.hostFilesystem = new Map(); // path -> content
  }

  createVolume(name) {
    if (!this.volumes.has(name)) {
      this.volumes.set(name, new Map());
      console.log(`[Docker Engine] Created Named Volume: '${name}'`);
    }
    return this.volumes.get(name);
  }

  writeToVolume(volumeName, filename, content) {
    const vol = this.volumes.get(volumeName);
    if (!vol) throw new Error(`Volume ${volumeName} does not exist!`);
    vol.set(filename, content);
    console.log(`📝 [Volume Write] '${volumeName}/${filename}' saved.`);
  }

  // Backup Helper Container: Mounts volume :ro and packs into tarball
  executeBackup(volumeName, hostBackupPath) {
    console.log(`\n🚀 [Helper Container] Starting ephemeral container (alpine:latest) with --rm...`);
    console.log(`   ↳ Mount 1: -v ${volumeName}:/data:ro (Safety Read-Only)`);
    console.log(`   ↳ Mount 2: -v $(pwd):/backup:rw`);

    const vol = this.volumes.get(volumeName);
    if (!vol) throw new Error(`Source volume ${volumeName} not found!`);

    // Serialize volume files into a mock compressed archive payload
    const archivePayload = JSON.stringify(Object.fromEntries(vol.entries()));
    const checksum = crypto.createHash('sha256').update(archivePayload).digest('hex');

    this.hostFilesystem.set(hostBackupPath, { payload: archivePayload, checksum });
    console.log(`📦 [tar -czvf] Created compressed archive at host: '${hostBackupPath}'`);
    console.log(`🔒 [SHA256 Checksum] ${checksum}`);
    console.log(`🛑 [Helper Container] Work complete. Ephemeral container terminated & removed.`);
    return checksum;
  }

  // Restore Helper Container: Extracts tarball into target volume
  executeRestore(hostBackupPath, targetVolumeName) {
    console.log(`\n🚀 [Helper Container] Starting ephemeral restore container...`);
    console.log(`   ↳ Mount 1: -v ${targetVolumeName}:/data:rw`);
    console.log(`   ↳ Mount 2: -v $(pwd):/backup:ro`);

    const backupFile = this.hostFilesystem.get(hostBackupPath);
    if (!backupFile) throw new Error(`Backup file ${hostBackupPath} not found!`);

    const targetVol = this.createVolume(targetVolumeName);
    const restoredEntries = JSON.parse(backupFile.payload);

    for (const [filename, content] of Object.entries(restoredEntries)) {
      targetVol.set(filename, content);
      console.log(`   ↳ [tar -xzvf] Extracted '${filename}' into '${targetVolumeName}'`);
    }

    console.log(`✅ [Restore Complete] Data successfully restored into '${targetVolumeName}'.`);
  }

  destroyVolume(volumeName) {
    if (this.volumes.has(volumeName)) {
      this.volumes.delete(volumeName);
      console.log(`💥 [docker volume rm] Destroyed volume: '${volumeName}'!`);
    }
  }

  pruneVolumes(activeVolumeNames = []) {
    console.log(`\n🧹 [docker volume prune -f] Scanning for dangling/orphaned volumes...`);
    let prunedCount = 0;
    for (const name of Array.from(this.volumes.keys())) {
      if (!activeVolumeNames.includes(name)) {
        this.volumes.delete(name);
        console.log(`   ↳ Deleted orphaned volume: '${name}'`);
        prunedCount++;
      }
    }
    console.log(`Pruned ${prunedCount} dangling volume(s). Disk space reclaimed.`);
  }
}

// -----------------------------------------------------------------
// LAB SIMULATION
// -----------------------------------------------------------------
async function runLab() {
  console.log(`======================================================`);
  console.log(`📦 DOCKER VOLUME BACKUP, RESTORE & MIGRATION LAB`);
  console.log(`======================================================\n`);

  const docker = new MockDockerStorageSystem();

  // STEP 1: Application writes important production data
  console.log(`--- STEP 1: PRODUCTION DATABASE WRITING DATA ---`);
  docker.createVolume('fintech_ledger_db');
  docker.writeToVolume('fintech_ledger_db', 'transactions_2026.sql', 'INSERT INTO ledger VALUES (101, "USD", 250000.00);');
  docker.writeToVolume('fintech_ledger_db', 'audit_trail.log', '2026-09-11: User admin verified audit chain.');

  // STEP 2: Ephemeral Helper Backup
  console.log(`\n--- STEP 2: RUNNING EPHEMERAL HELPER BACKUP ---`);
  const backupPath = '/home/backup/fintech_ledger_20260911.tar.gz';
  const originalChecksum = docker.executeBackup('fintech_ledger_db', backupPath);

  // STEP 3: Disaster Simulation (Accidental Volume Deletion)
  console.log(`\n--- STEP 3: SIMULATING HARD DRIVE CORRUPTION / DISASTER ---`);
  docker.destroyVolume('fintech_ledger_db');

  // STEP 4: Disaster Recovery (Restore to New Volume)
  console.log(`\n--- STEP 4: EXECUTING DISASTER RECOVERY RESTORE ---`);
  docker.executeRestore(backupPath, 'fintech_ledger_restored');

  // STEP 5: Integrity Verification
  console.log(`\n--- STEP 5: VERIFYING RESTORED DATA INTEGRITY ---`);
  const restoredVol = docker.volumes.get('fintech_ledger_restored');
  const restoredPayload = JSON.stringify(Object.fromEntries(restoredVol.entries()));
  const restoredChecksum = crypto.createHash('sha256').update(restoredPayload).digest('hex');

  console.log(`Original Backup Checksum : ${originalChecksum}`);
  console.log(`Restored Volume Checksum : ${restoredChecksum}`);

  if (originalChecksum === restoredChecksum) {
    console.log(`🎉 [INTEGRITY CHECK PASSED] 100% Data matching! Zero byte loss or corruption.`);
  } else {
    console.error(`❌ [INTEGRITY CHECK FAILED] Checksums do not match!`);
  }

  // STEP 6: Garbage Collection / Prune Demo
  console.log(`\n--- STEP 6: VOLUME HYGIENE & PRUNING ---`);
  docker.createVolume('abandoned_temp_vol_1');
  docker.createVolume('abandoned_temp_vol_2');
  docker.pruneVolumes(['fintech_ledger_restored']); // Only keep fintech_ledger_restored

  console.log(`\n🎉 Volume Backup, Restore, & Prune Pipeline Complete!`);
}

runLab();
