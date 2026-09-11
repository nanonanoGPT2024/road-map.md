/**
 * hands-on/m02/init_sidecar_pattern_sim.js
 * 
 * Simulasi Pola Multi-Container Kubernetes:
 * 1. Init Containers Sequential Lifecycle (Dependency Check -> DB Migration -> Exit 0).
 * 2. Shared Memory/Volume (emptyDir) Data Exchange between containers.
 * 3. Native Sidecar Container (Background log tailing & metric shipping).
 * 4. Ambassador Proxy Routing (localhost:6379 -> Remote Shards).
 * 5. Ephemeral Debug Container Injection into running Pod Sandbox.
 */

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

console.log("================================================================================");
console.log("       KUBERNETES MULTI-CONTAINER PATTERNS & EPHEMERAL DEBUG SIMULATOR          ");
console.log("================================================================================\n");

class MultiContainerPodSimulator {
    constructor(podName) {
        this.podName = podName;
        this.sharedVolume = new Map(); // Simulates emptyDir volume
        this.podState = "Pending";
        this.initContainers = [];
        this.appContainers = [];
        this.sidecars = [];
        this.ephemeralContainers = [];
    }

    log(component, msg) {
        const ts = new Date().toISOString().substring(11, 19);
        console.log(`[${ts}] [${component.padEnd(16)}] ${msg}`);
    }

    // Step 1: Execute Init Containers sequentially
    async runInitContainers(configs) {
        console.log("=== FASE 1: EKSEKUSI INIT CONTAINERS (SEKUENSIAL & BLOCKING) ===");
        this.podState = "Init:0/" + configs.length;

        for (let i = 0; i < configs.length; i++) {
            const init = configs[i];
            this.podState = `Init:${i}/${configs.length}`;
            this.log("INIT_CONTAINER", `Memulai [${init.name}] -> Command: "${init.command}"`);
            await sleep(150);

            if (init.shouldFail) {
                this.log("INIT_CONTAINER", `  [CRITICAL ERROR] [${init.name}] keluar dengan status non-zero: Exit Code 1!`);
                this.podState = "Init:CrashLoopBackOff";
                this.log("KUBELET", `Pod terjebak pada status: [${this.podState}]. Kontainer aplikasi UTAMA TIDAK AKAN PERNAH DIJALANKAN!\n`);
                return false;
            }

            // Simulate writing shared configuration
            if (init.outputFile) {
                this.sharedVolume.set(init.outputFile, init.outputData);
                this.log("SHARED_VOLUME", `  [emptyDir Mount] Berhasil menulis file konfigurasi: ${init.outputFile}`);
            }

            this.log("INIT_CONTAINER", `  [SUCCESS] [${init.name}] selesai secara normal (Exit Code 0).`);
        }

        this.log("KUBELET", `Seluruh Init Containers (${configs.length}/${configs.length}) sukses selesai!\n`);
        return true;
    }

    // Step 2: Start Main App & Native Sidecar
    async startAppAndSidecar() {
        console.log("=== FASE 2: MEMULAI APLIKASI UTAMA & NATIVE SIDECAR ===");
        this.podState = "Running";

        // Read configuration from shared volume created by Init Container
        const configData = this.sharedVolume.get("/config/app.json");
        this.log("MAIN_APP", `Kontainer 'checkout-api' start! Membaca shared volume: ${configData}`);

        // Native Sidecar Tailer
        this.log("SIDECAR_LOGS", `Native Sidecar 'promtail-tailer' aktif (restartPolicy: Always).`);
        this.log("SIDECAR_LOGS", `Memantau log streaming dari /var/log/checkout.log di shared volume.`);

        // Ambassador Proxy
        this.log("AMBASSADOR", `Ambassador 'redis-proxy' mendengarkan di localhost:6379.`);
        this.log("AMBASSADOR", `Merutekan traffic cache ke remote Redis cluster (Shard-01).`);
        console.log("");
    }

    // Step 3: Inject Ephemeral Container for Live Debugging
    async injectEphemeralContainer(imageName, command) {
        console.log("=== FASE 3: INJEKSI EPHEMERAL CONTAINER (LIVE DEBUGGING) ===");
        this.log("APISERVER_API", `Menerima request: kubectl debug -it ${this.podName} --image=${imageName}`);
        this.log("KUBELET_CRI", `gRPC RuntimeService.CreateContainer (Ephemeral: debug-shell) di Pod Sandbox aktif!`);
        await sleep(150);

        this.ephemeralContainers.push({
            name: "debugger-toolbox",
            image: imageName,
            status: "Running"
        });

        this.log("EPHEMERAL_CTR", `[SHELL READY] Container '${imageName}' bergabung ke Network Namespace & PID Namespace Pod!`);
        this.log("EPHEMERAL_CTR", `Mengeksekusi command forensik: "${command}"`);
        this.log("EPHEMERAL_CTR", `  -> Output: Probing localhost:8080... HTTP 200 OK (Latency: 1.2ms)`);
        this.log("EPHEMERAL_CTR", `  -> Output: Active TCP Connections: 14 sockets open. Memory RSS: 142MB.`);
        this.log("EPHEMERAL_CTR", `Sesi debug selesai. Ephemeral container dihentikan tanpa mengganggu aplikasi utama.\n`);
    }
}

async function run() {
    const pod = new MultiContainerPodSimulator("payflow-order-pod");

    // Skenario Init Containers
    const initSteps = [
        {
            name: "wait-for-postgres",
            command: "nc -z -v -w3 postgres 5432",
            shouldFail: false
        },
        {
            name: "db-schema-migration",
            command: "prisma migrate deploy",
            outputFile: "/config/app.json",
            outputData: JSON.stringify({ dbVersion: "2.4.0", maintenanceMode: false }),
            shouldFail: false
        }
    ];

    const initOk = await pod.runInitContainers(initSteps);
    if (!initOk) return;

    await pod.startAppAndSidecar();

    // Skenario Injeksi Ephemeral Container pada kontainer distroless
    await pod.injectEphemeralContainer("nicolaka/netshoot", "curl -I localhost:8080 && netstat -tuln");

    console.log("=== KESIMPULAN ARSITEKTUR MULTI-CONTAINER ===");
    console.log("1. Init Container memvalidasi prasyarat (DB ready) sebelum app start.");
    console.log("2. Shared emptyDir volume memungkinkan pertukaran file instan antar kontainer.");
    console.log("3. Ambassador dan Sidecar mengisolasi concern non-bisnis (proxying & logging).");
    console.log("4. Ephemeral container adalah penyelamat debugging untuk image produksi distroless.");
}

run().catch(console.error);
