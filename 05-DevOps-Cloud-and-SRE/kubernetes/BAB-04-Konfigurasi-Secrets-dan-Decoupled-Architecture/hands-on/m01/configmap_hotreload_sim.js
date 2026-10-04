/**
 * hands-on/m01/configmap_hotreload_sim.js
 * 
 * Simulasi ConfigMap, Atomic Symlink Rotation, Downward API, & Hot-Reload:
 * 1. Env Var vs Volume Mount Update Behavior (Stale vs Live).
 * 2. Kubelet Atomic Symlink Rotation Engine (..data -> ..timestamp_dir).
 * 3. Downward API Metadata Injection (Pod Name, IP, Node Name, Limits).
 * 4. Checksum Annotation Rollout Trigger ("checksum/config").
 */

const crypto = require('crypto');

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

console.log("================================================================================");
console.log("    KUBERNETES CONFIGMAP ATOMIC SYMLINK & HOT-RELOAD SIMULATOR v1.6             ");
console.log("================================================================================\n");

class ConfigMapEngineSimulator {
    constructor() {
        this.configMapData = {
            LOG_LEVEL: "INFO",
            MAX_CONNECTIONS: "50",
            FEATURES_JSON: JSON.stringify({ enableNewUi: false, maintenance: false })
        };
        this.envVarSnapshot = null;
        this.mountedFilesystem = new Map();
        this.activeSymlinkTarget = null;
    }

    log(subsystem, msg) {
        const ts = new Date().toISOString().substring(11, 19);
        console.log(`[${ts}] [${subsystem.padEnd(16)}] ${msg}`);
    }

    // Step 1: Initialize Downward API & Pod Environment
    initPodEnvironment() {
        console.log("=== TAHAP 1: DOWNWARD API & ENV VAR INJECTION ===");
        
        // Simulating Downward API injection
        const downwardApi = {
            POD_NAME: "payment-service-7b9d4f-x82w",
            POD_NAMESPACE: "fintech-production",
            POD_IP: "10.244.2.89",
            NODE_NAME: "k8s-worker-zone-1b",
            CPU_LIMIT: "2000m",
            MEMORY_LIMIT: "1073741824" // 1 GiB
        };

        this.log("DOWNWARD_API", "Mengekstrak metadata topologi Pod ke proses kontainer:");
        for (const [key, val] of Object.entries(downwardApi)) {
            this.log("DOWNWARD_API", `  -> export ${key}="${val}"`);
        }

        // Snapshot ConfigMap to process.env (Static snapshot)
        this.envVarSnapshot = { ...this.configMapData };
        this.log("ENV_INJECTION", `Injeksi envFrom ConfigMap: LOG_LEVEL="${this.envVarSnapshot.LOG_LEVEL}"\n`);
    }

    // Step 2: Initialize Volume Mount with Symlink Rotation Structure
    initVolumeMount() {
        console.log("=== TAHAP 2: KUBELET VOLUME MOUNT & SYMLINK INITIALIZATION ===");
        const timestamp = new Date().toISOString().replace(/[-:T.]/g, '_').substring(0, 19);
        const dataDirName = `..${timestamp}`;

        // Store file content in timestamped directory
        this.mountedFilesystem.set(`${dataDirName}/app_config.json`, this.configMapData.FEATURES_JSON);
        this.activeSymlinkTarget = dataDirName;

        this.log("KUBELET_FS", `Membuat mount path: /etc/payment/config/`);
        this.log("KUBELET_FS", `  -> Direktori beralamat: /etc/payment/config/${dataDirName}/`);
        this.log("KUBELET_FS", `  -> Atomic Symlink: /etc/payment/config/..data -> ${dataDirName}`);
        this.log("KUBELET_FS", `  -> File Pointer:   /etc/payment/config/app_config.json -> ..data/app_config.json\n`);
    }

    // Step 3: Update ConfigMap in Kubernetes Cluster
    async updateConfigMapInCluster(newLogLevel, newFeatures) {
        console.log("=== TAHAP 3: PEMBARUAN CONFIGMAP DI LEVEL KUBERNETES CLUSTER ===");
        this.log("APISERVER", `Operator menjalankan: kubectl edit configmap payment-config`);
        this.configMapData.LOG_LEVEL = newLogLevel;
        this.configMapData.FEATURES_JSON = JSON.stringify(newFeatures);
        this.log("APISERVER", `Data baru tersimpan di etcd: LOG_LEVEL="${newLogLevel}", Features=${this.configMapData.FEATURES_JSON}\n`);

        await sleep(200);

        // Simulate Kubelet periodic sync (Atomic Symlink Swap)
        console.log("=== TAHAP 4: KUBELET ATOMIC SYMLINK ROTATION (BACKGROUND SYNC) ===");
        const newTimestamp = new Date().toISOString().replace(/[-:T.]/g, '_').substring(0, 19) + "_v2";
        const newDataDir = `..${newTimestamp}`;

        // 1. Tulis konten ke direktori baru
        this.mountedFilesystem.set(`${newDataDir}/app_config.json`, this.configMapData.FEATURES_JSON);
        this.log("KUBELET_SYNC", `1. Menulis data baru ke direktori sementara: ${newDataDir}/`);
        await sleep(150);

        // 2. Atomic pointer swap
        this.activeSymlinkTarget = newDataDir;
        this.log("KUBELET_SYNC", `2. Syscall rename(): Memutar symlink '..data' secara atomik ke -> ${newDataDir}`);
        this.log("KUBELET_SYNC", `3. Menghapus direktori usang lama secara aman.`);
        this.log("KUBELET_SYNC", `[SUKSES] Volume filesystem ter-update tanpa memutus pembacaan file!\n`);
    }

    // Step 4: Verification of App Reading Env vs Volume
    readApplicationState() {
        console.log("=== TAHAP 5: VERIFIKASI PEMBACAAN APLIKASI (ENV VS VOLUME) ===");
        
        // Check Environment Variable State
        console.log(`[PEMERIKSAAN ENVIRONMENT VARIABLE (process.env)]`);
        console.log(`  -> Current process.env.LOG_LEVEL: "${this.envVarSnapshot.LOG_LEVEL}"`);
        if (this.envVarSnapshot.LOG_LEVEL !== this.configMapData.LOG_LEVEL) {
            console.log(`  ❌ [STALE DATA!] Nilai env var TIDAK BERUBAH meskipun ConfigMap sudah diganti! (Butuh Restart Pod)`);
        } else {
            console.log(`  ✅ [UP TO DATE]`);
        }
        console.log("");

        // Check Volume File State via active symlink
        console.log(`[PEMERIKSAAN VOLUME MOUNT (/etc/payment/config/app_config.json)]`);
        const fileContent = this.mountedFilesystem.get(`${this.activeSymlinkTarget}/app_config.json`);
        console.log(`  -> Membaca file melalui symlink ..data/app_config.json:`);
        console.log(`     ${fileContent}`);
        console.log(`  ✅ [LIVE UPDATED!] Aplikasi langsung membaca konfigurasi terbaru tanpa perlu me-restart kontainer!\n`);
    }

    // Step 5: Checksum Hash Annotation Demo
    calculateConfigHash() {
        const hash = crypto.createHash('sha256').update(JSON.stringify(this.configMapData)).digest('hex').substring(0, 16);
        console.log(`=== TAHAP 6: CHECKSUM ANNOTATION TRICK ===`);
        console.log(`Deployment Spec Annotation: "checksum/config: ${hash}"`);
        console.log(`Ketika hash berubah, ReplicaSet otomatis mendeteksi perbedaan template dan memicu RollingUpdate!\n`);
        return hash;
    }
}

async function run() {
    const sim = new ConfigMapEngineSimulator();

    // 1. Inisialisasi Pod
    sim.initPodEnvironment();
    sim.initVolumeMount();

    // 2. Hitung hash awal
    sim.calculateConfigHash();

    // 3. Ubah ConfigMap (misal saat insiden: ubah log level ke DEBUG dan aktifkan fitur)
    await sim.updateConfigMapInCluster("DEBUG", { enableNewUi: true, maintenance: false });

    // 4. Periksa perilaku aplikasi
    sim.readApplicationState();

    // 5. Hitung hash baru
    sim.calculateConfigHash();

    console.log("=== KESIMPULAN REKOMENDASI PRODUKSI ===");
    console.log("1. Environment variables bersifat STATIC (tidak auto-update tanpa restart).");
    console.log("2. Volume mounts mendukung LIVE HOT-RELOAD via atomic symlink '..data'.");
    console.log("3. Hindari 'subPath' jika Anda ingin memanfaatkan auto-update volume mount.");
}

run().catch(console.error);
