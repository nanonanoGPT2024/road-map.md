/**
 * hands-on/m01/rolling_update_deployer_sim.js
 * 
 * Simulasi Deployment Controller, RollingUpdate Engine, & Automated Rollbacks:
 * 1. ReplicaSet Generation & Pod Template Hash Tracking.
 * 2. RollingUpdate Algorithm (maxSurge: 1, maxUnavailable: 0).
 * 3. Throttled Surge & Drain Loop with Readiness Probe Verification.
 * 4. Hung Rollout Detection (Broken v2.1.0 image probe).
 * 5. Instant Rollback Engine ("kubectl rollout undo").
 */

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

console.log("================================================================================");
console.log("    KUBERNETES DEPLOYMENT ROLLING UPDATE & ROLLBACK ENGINE SIMULATOR v2.2       ");
console.log("================================================================================\n");

class RollingUpdateEngineSimulator {
    constructor(deploymentName, targetReplicas = 4, maxSurge = 1, maxUnavailable = 0) {
        this.deploymentName = deploymentName;
        this.targetReplicas = targetReplicas;
        this.maxSurge = maxSurge;
        this.maxUnavailable = maxUnavailable;
        this.replicaSets = new Map(); // revision -> RS object
        this.currentRevision = 1;
    }

    log(component, msg) {
        const ts = new Date().toISOString().substring(11, 19);
        console.log(`[${ts}] [${component.padEnd(16)}] ${msg}`);
    }

    // Step 1: Initialize Deployment with Revision 1
    initDeployment(image) {
        const rsName = `${this.deploymentName}-${Math.random().toString(36).substring(2, 8)}`;
        const initialRs = {
            revision: 1,
            name: rsName,
            image: image,
            replicas: this.targetReplicas,
            healthyPods: this.targetReplicas
        };
        this.replicaSets.set(1, initialRs);
        this.log("DEPLOY_INIT", `Deployment "${this.deploymentName}" aktif dengan ${this.targetReplicas} replika (Image: ${image})`);
        this.log("DEPLOY_INIT", `ReplicaSet dibuat: "${rsName}" (Revision 1, Healthy: ${initialRs.healthyPods}/${this.targetReplicas})\n`);
    }

    // Step 2: Trigger Rolling Update to New Image
    async performRollingUpdate(newImage, simulateBrokenProbe = false) {
        this.currentRevision++;
        const newRev = this.currentRevision;
        const newRsName = `${this.deploymentName}-${Math.random().toString(36).substring(2, 8)}`;
        
        const oldRs = this.replicaSets.get(newRev - 1);
        const newRs = {
            revision: newRev,
            name: newRsName,
            image: newImage,
            replicas: 0,
            healthyPods: 0
        };
        this.replicaSets.set(newRev, newRs);

        console.log(`=== MEMULAI ROLLING UPDATE KE REVISI ${newRev} (${newImage}) ===`);
        this.log("DEPLOY_CTRL", `Strategi: maxSurge=${this.maxSurge}, maxUnavailable=${this.maxUnavailable}`);
        this.log("DEPLOY_CTRL", `Maksimum Pods yang diizinkan selama rollout: ${this.targetReplicas + this.maxSurge}`);
        this.log("DEPLOY_CTRL", `Minimum Pods sehat yang wajib tersedia: ${this.targetReplicas - this.maxUnavailable}\n`);

        let step = 1;
        while (newRs.healthyPods < this.targetReplicas) {
            console.log(`--- [Langkah ${step}] Transisi Rolling Update ---`);
            
            // 2.1 Surge: Tambah Pod di RS Baru jika batas maxSurge belum tercapai
            const totalPods = oldRs.healthyPods + newRs.healthyPods;
            if (totalPods < this.targetReplicas + this.maxSurge && newRs.replicas < this.targetReplicas) {
                newRs.replicas++;
                this.log("RS_CONTROLLER", `[SURGE] Menambah Pod baru di ${newRs.name} (Total Pods direncanakan: ${newRs.replicas})`);
                await sleep(150);

                if (simulateBrokenProbe) {
                    this.log("READINESS_PROBE", `[CRITICAL FAIL] Pod baru di ${newRs.name} gagal readinessProbe (HTTP 503)!`);
                    this.log("DEPLOY_CTRL", `[ROLLOUT HALTED] maxUnavailable: 0 mencegah pembongkaran Pod lama.`);
                    this.log("DEPLOY_CTRL", `Sistem aman: 4 Pod lama (v1.0.0) tetap melayani traffic 100% tanpa downtime!\n`);
                    return { success: false, failedRevision: newRev };
                }

                // Simulate healthy probe
                newRs.healthyPods++;
                this.log("READINESS_PROBE", `Pod baru lolos readinessProbe (200 OK)! Healthy pods v${newRev}: ${newRs.healthyPods}/${this.targetReplicas}`);
            }

            // 2.2 Drain: Turunkan Pod di RS Lama karena Pod baru sudah sehat
            if (oldRs.healthyPods > 0) {
                oldRs.healthyPods--;
                oldRs.replicas--;
                this.log("RS_CONTROLLER", `[DRAIN] Mengurangi 1 Pod dari ${oldRs.name} (Sisa Pod lama: ${oldRs.healthyPods})`);
                await sleep(100);
            }

            this.log("STATUS_CHECK", `Kapasitas Aktif Saat Ini: ${oldRs.healthyPods} (Versi Lama) + ${newRs.healthyPods} (Versi Baru) = ${oldRs.healthyPods + newRs.healthyPods} Pods Sehat.\n`);
            step++;
        }

        this.log("DEPLOY_CTRL", `[SUKSES] Rolling update selesai! 100% workload kini dilayani oleh ${newRs.name} (${newImage}).\n`);
        return { success: true, activeRevision: newRev };
    }

    // Step 3: Rollback ("kubectl rollout undo")
    async rollbackToRevision(targetRev) {
        console.log(`=== EKSEKUSI ROLLBACK INSTAN: "kubectl rollout undo" ===`);
        const targetRs = this.replicaSets.get(targetRev);
        const currentRs = this.replicaSets.get(this.currentRevision);

        if (!targetRs) {
            this.log("ROLLBACK", `[ERROR] Target revisi ${targetRev} tidak ditemukan di history!`);
            return;
        }

        this.log("ROLLBACK", `Membatalkan rilis yang gagal. Mengembalikan state ke Revisi ${targetRev} (${targetRs.image})...`);
        await sleep(200);

        // Terminate unready failed pods
        currentRs.replicas = 0;
        currentRs.healthyPods = 0;
        this.log("RS_CONTROLLER", `Mematikan seluruh Pod gagal di ${currentRs.name}...`);

        // Re-scale target healthy ReplicaSet
        targetRs.replicas = this.targetReplicas;
        targetRs.healthyPods = this.targetReplicas;
        this.log("RS_CONTROLLER", `Memulihkan ${targetRs.name} ke ${this.targetReplicas} replika sehat.`);
        this.log("ROLLBACK", `[SUCCESS] Rollback selesai dalam 400ms! Kluster kembali stabil 100% di ${targetRs.image}.\n`);
    }
}

async function run() {
    const deployer = new RollingUpdateEngineSimulator("payment-api", 4, 1, 0);

    // 1. Initial State: v1.0.0
    deployer.initDeployment("payflow/api:v1.0.0");

    // 2. Successful Rolling Update to v2.0.0
    await deployer.performRollingUpdate("payflow/api:v2.0.0", false);

    // 3. Flawed Deployment to v2.1.0 with broken probe
    const result = await deployer.performRollingUpdate("payflow/api:v2.1.0-broken", true);

    if (!result.success) {
        // 4. Trigger Instant Rollback to v2.0.0
        await deployer.rollbackToRevision(2);
    }

    console.log("=== RINGKASAN REVISI REPLICASET ===");
    for (const [rev, rs] of deployer.replicaSets.entries()) {
        console.log(`Revisi ${rev}: [${rs.name}] Image: ${rs.image.padEnd(26)} -> Healthy Replicas: ${rs.healthyPods}`);
    }
    console.log("");
}

run().catch(console.error);
