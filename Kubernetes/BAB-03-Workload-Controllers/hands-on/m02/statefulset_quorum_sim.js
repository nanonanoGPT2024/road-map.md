/**
 * hands-on/m02/statefulset_quorum_sim.js
 * 
 * Simulasi Workload Controllers Lanjutan:
 * 1. StatefulSet Ordered Sequential Bootstrapping (app-0 -> app-1 -> app-2).
 * 2. Dedicated Persistent Storage Binding (volumeClaimTemplates retention).
 * 3. Headless Service FQDN DNS Resolution (peer-to-peer clustering).
 * 4. DaemonSet Node Footprint Guarantee.
 * 5. CronJob Concurrency Policy Engine (Forbid vs Allow behavior).
 */

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

console.log("================================================================================");
console.log("     KUBERNETES STATEFULSET, DAEMONSET, & CRONJOB CONTROLLERS SIMULATOR         ");
console.log("================================================================================\n");

class StatefulSetSimulator {
    constructor(name, replicas = 3) {
        this.name = name;
        this.replicas = replicas;
        this.pods = [];
        this.pvcStore = new Map(); // Simulates volumeClaimTemplates
        this.dnsRegistry = new Map(); // Headless service DNS
    }

    log(component, msg) {
        const ts = new Date().toISOString().substring(11, 19);
        console.log(`[${ts}] [${component.padEnd(16)}] ${msg}`);
    }

    // Step 1: Sequential Ordered Bootstrapping
    async deployStatefulSet() {
        console.log(`=== TAHAP 1: STATEFULSET ORDERED INITIALIZATION (${this.name}) ===`);
        this.log("STATEFUL_CTRL", `Memulai inisialisasi StatefulSet: ${this.replicas} replika berurutan (0 ke ${this.replicas - 1})...`);

        for (let i = 0; i < this.replicas; i++) {
            const podName = `${this.name}-${i}`;
            const pvcName = `datadir-${podName}`;
            const podIp = `10.244.${i + 1}.${10 + i}`;
            const fqdn = `${podName}.${this.name}-headless.default.svc.cluster.local`;

            this.log("STATEFUL_CTRL", `[Urutan #${i}] Menjadwalkan Pod: "${podName}"...`);
            await sleep(150);

            // Bind PVC
            if (!this.pvcStore.has(pvcName)) {
                this.pvcStore.set(pvcName, { volumeId: `vol-ebs-00${i + 1}`, size: "50Gi", bound: true });
                this.log("PVC_PROVISION", `  -> volumeClaimTemplates membuat ${pvcName} (AWS EBS vol-ebs-00${i + 1})`);
            }

            // Register Headless DNS
            this.dnsRegistry.set(fqdn, podIp);
            this.log("HEADLESS_DNS", `  -> Mendaftarkan FQDN: ${fqdn} -> IP ${podIp}`);

            this.pods.push({ name: podName, ip: podIp, status: "Ready" });
            this.log("STATEFUL_CTRL", `  -> Pod "${podName}" READY! Melanjutkan ke urutan berikutnya...\n`);
            await sleep(100);
        }

        this.log("STATEFUL_CTRL", `Seluruh replika StatefulSet aktif dalam kondisi sehat dan sinkron!\n`);
    }

    // Step 2: Pod Reschedule Simulation (Preserving Storage & Identity)
    async simulateNodeCrashAndRecovery(podIndex) {
        console.log(`=== TAHAP 2: SIMULASI PEMULIHAN NODE MATI PADA STATEFULSET ===`);
        const targetPod = `${this.name}-${podIndex}`;
        const targetPvc = `datadir-${targetPod}`;
        const fqdn = `${targetPod}.${this.name}-headless.default.svc.cluster.local`;

        this.log("NODE_CRASH", `Worker node tempat "${targetPod}" berjalan tiba-tiba mati!`);
        this.log("STATEFUL_CTRL", `Menjadwalkan ulang "${targetPod}" ke node sehat lain...`);
        await sleep(200);

        const oldVolume = this.pvcStore.get(targetPvc);
        this.log("PVC_REBIND", `  -> [STORAGE PERSISTED] Meng-attach kembali disk yang sama (${oldVolume.volumeId}) ke ${targetPod}!`);
        
        const newIp = `10.244.4.99`;
        this.dnsRegistry.set(fqdn, newIp);
        this.log("HEADLESS_DNS", `  -> [DNS REFRESH] FQDN ${fqdn} diperbarui menunjuk ke IP baru: ${newIp}`);
        this.log("STATEFUL_CTRL", `  -> Identitas "${targetPod}" tetap utuh, data disk 100% aman tanpa re-sync!\n`);
    }
}

// Step 3: DaemonSet Scheduling Simulator
class DaemonSetSimulator {
    static deployDaemonSet(name, nodes) {
        console.log(`=== TAHAP 3: DAEMONSET GUARANTEE ENGINE (${name}) ===`);
        console.log(`Mengevaluasi ${nodes.length} node di kluster untuk penempatan tepat 1 Pod per node:`);
        
        nodes.forEach(node => {
            if (node.isControlPlane && !node.hasToleration) {
                console.log(`  [SKIPPED] Node "${node.name}" memiliki taint 'node-role.kubernetes.io/control-plane:NoSchedule' (Tanpa Toleration)`);
            } else {
                console.log(`  [DEPLOYED] Node "${node.name}" -> Menjalankan Pod '${name}-${node.name.substring(0, 8)}' (OK)`);
            }
        });
        console.log("");
    }
}

// Step 4: CronJob Concurrency Policy Simulator
class CronJobSimulator {
    static async simulateConcurrencyPolicy(policy = "Forbid") {
        console.log(`=== TAHAP 4: CRONJOB CONCURRENCY POLICY SIMULATION (Mode: ${policy}) ===`);
        console.log(`Skenario: Jadwal Cron terpicu setiap 1 detik, tetapi eksekusi task butuh 3 detik.`);

        let isJob1Running = true;
        console.log(`[T=0s] Job-1 mulai berjalan... (Proses backup database besar)`);

        await sleep(200);
        console.log(`[T=1s] Jadwal kedua tiba! Memeriksa kebijakan 'concurrencyPolicy: ${policy}'...`);

        if (policy === "Forbid") {
            console.log(`  -> [ACTION: FORBID] Job-2 DIBATALKAN / DILEWATI karena Job-1 masih berjalan! Mencegah database lock.`);
        } else if (policy === "Allow") {
            console.log(`  -> [ACTION: ALLOW] Job-2 DIJALANKAN bersamaan dengan Job-1! (Beban server meningkat ganda)`);
        }

        await sleep(200);
        isJob1Running = false;
        console.log(`[T=3s] Job-1 berhasil selesai secara normal (Exit 0).\n`);
    }
}

async function run() {
    // 1. StatefulSet Test
    const kafkaCluster = new StatefulSetSimulator("kafka", 3);
    await kafkaCluster.deployStatefulSet();

    // 2. Recovery on Kafka-1
    await kafkaCluster.simulateNodeCrashAndRecovery(1);

    // 3. DaemonSet Test
    const clusterNodes = [
        { name: "k8s-master-01", isControlPlane: true, hasToleration: false },
        { name: "k8s-worker-01", isControlPlane: false, hasToleration: false },
        { name: "k8s-worker-02", isControlPlane: false, hasToleration: false },
        { name: "k8s-worker-03", isControlPlane: false, hasToleration: false }
    ];
    DaemonSetSimulator.deployDaemonSet("fluent-bit-logger", clusterNodes);

    // 4. CronJob Policy Test
    await CronJobSimulator.simulateConcurrencyPolicy("Forbid");

    console.log("=== KESIMPULAN ARSITEKTUR CONTROLLERS ===");
    console.log("1. StatefulSet mempertahankan FQDN DNS dan Disk PVC permanen.");
    console.log("2. DaemonSet menjamin agen monitoring ada di setiap worker host.");
    console.log("3. Gunakan 'concurrencyPolicy: Forbid' pada CronJob data processing.");
}

run().catch(console.error);
