/**
 * hands-on/m01/pod_probes_lifecycle_sim.js
 * 
 * Simulasi Pod Health Probes & Graceful Termination:
 * 1. Startup Probe: Menahan probe lain saat aplikasi lambat bootstrapping.
 * 2. Readiness Probe: Mengontrol pendaftaran IP Pod ke Service Endpoints (tanpa restart).
 * 3. Liveness Probe: Mendeteksi deadlock memori & memicu restart kontainer.
 * 4. Graceful Termination Pipeline: preStop hook -> SIGTERM -> in-flight drain -> clean exit 0.
 */

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

console.log("================================================================================");
console.log("       KUBERNETES POD PROBES & GRACEFUL TERMINATION SIMULATOR v2.0              ");
console.log("================================================================================\n");

class PodLifecycleSimulator {
    constructor(podName, ip = "10.244.1.75") {
        this.podName = podName;
        this.ip = ip;
        this.bootProgress = 0; // 0 to 100
        this.dbConnected = false;
        this.isDeadlocked = false;
        this.inFlightRequests = 0;
        this.serviceEndpoints = new Set();
        this.restartCount = 0;
        this.livenessFailures = 0;
    }

    log(stage, msg) {
        const ts = new Date().toISOString().substring(11, 19);
        console.log(`[${ts}] [${stage.padEnd(15)}] ${msg}`);
    }

    // Step 1: Startup Probe Simulator
    async runStartupProbe(maxAttempts = 5) {
        this.log("STARTUP_PROBE", `Memulai pengawasan startupProbe (/healthz/startup)...`);
        for (let attempt = 1; attempt <= maxAttempts; attempt++) {
            await sleep(150);
            this.bootProgress += 30;
            if (this.bootProgress >= 80) {
                this.log("STARTUP_PROBE", `  [Attempt ${attempt}: SUCCESS] Aplikasi selesai inisialisasi framework & cache!`);
                this.log("STARTUP_PROBE", `  -> startupProbe LULUS. Mengaktifkan livenessProbe & readinessProbe.\n`);
                return true;
            } else {
                this.log("STARTUP_PROBE", `  [Attempt ${attempt}: PENDING] Booting progress ${this.bootProgress}% (Waiting for DB pool...)`);
            }
        }
        return false;
    }

    // Step 2: Readiness Probe Simulator
    evaluateReadiness() {
        this.log("READINESS_PROBE", `Pemeriksaan /healthz/ready: DB_CONNECTED=${this.dbConnected}`);
        if (this.dbConnected && !this.isDeadlocked) {
            if (!this.serviceEndpoints.has(this.ip)) {
                this.serviceEndpoints.add(this.ip);
                this.log("READINESS_PROBE", `  [STATUS: READY] Pod Condition: "Ready=True".`);
                this.log("SERVICE_ROUTER", `  [ENDPOINT ADDED] Menambahkan IP ${this.ip} ke upstream Service. Menerima traffic!`);
            } else {
                this.log("READINESS_PROBE", `  [STATUS: READY] Pod tetap melayani traffic.`);
            }
        } else {
            if (this.serviceEndpoints.has(this.ip)) {
                this.serviceEndpoints.delete(this.ip);
                this.log("READINESS_PROBE", `  [STATUS: NOT READY] Pod Condition: "Ready=False".`);
                this.log("SERVICE_ROUTER", `  [ENDPOINT REMOVED] Mencabut IP ${this.ip} dari upstream Service! Traffic dialihkan ke Pod lain.`);
                this.log("READINESS_PROBE", `  (Catatan: Kontainer TIDAK di-restart, hanya diisolasi sementara)`);
            } else {
                this.log("READINESS_PROBE", `  [STATUS: NOT READY] Menunggu dependensi siap...`);
            }
        }
        console.log("");
    }

    // Step 3: Liveness Probe Simulator
    evaluateLiveness() {
        this.log("LIVENESS_PROBE", `Pemeriksaan /healthz/liveness (Deadlock Check)...`);
        if (this.isDeadlocked) {
            this.livenessFailures++;
            this.log("LIVENESS_PROBE", `  [FAIL ${this.livenessFailures}/3] Thread pool unresponsive! Deadlock terdeteksi.`);
            if (this.livenessFailures >= 3) {
                this.restartCount++;
                this.log("KUBELET_ACTION", `  [FAILURE THRESHOLD REACHED] Kubelet membunuh kontainer & memicu RESTART! (Restart #${this.restartCount})`);
                this.isDeadlocked = false;
                this.livenessFailures = 0;
                this.log("KUBELET_ACTION", `  Kontainer baru bangkit kembali secara sehat.\n`);
            }
        } else {
            this.livenessFailures = 0;
            this.log("LIVENESS_PROBE", `  [PASS] Event-loop sehat, respon 200 OK dalam 4ms.\n`);
        }
    }

    // Step 4: Graceful Termination Simulator
    async terminateGracefully() {
        console.log("=== MEMULAI SIKLUS HIDUP GRACEFUL TERMINATION ===");
        this.log("APISERVER_CMD", `Menerima instruksi: kubectl delete pod ${this.podName}`);
        
        // 1. Cabut IP dari Service
        this.serviceEndpoints.delete(this.ip);
        this.log("SERVICE_ROUTER", `Mencabut IP ${this.ip} dari Service Endpoints. Tidak ada request baru masuk.`);

        // 2. PreStop hook
        this.log("PRESTOP_HOOK", `Mengeksekusi lifecycle.preStop: sleep 3s (Memberi waktu update iptables di seluruh worker nodes)...`);
        this.inFlightRequests = 3; // Sedang ada 3 transaksi checkout nasabah
        await sleep(300);

        // 3. Send SIGTERM
        this.log("KUBELET_SIGNAL", `Kubelet mengirimkan sinyal SIGTERM (Signal 15) ke PID 1 kontainer.`);
        this.log("APP_HANDLER", `Aplikasi menangkap SIGTERM. Menyelesaikan ${this.inFlightRequests} transaksi checkout aktif...`);
        
        while (this.inFlightRequests > 0) {
            await sleep(100);
            this.inFlightRequests--;
            this.log("APP_HANDLER", `  Transaksi selesai diproses. Sisa transaksi aktif: ${this.inFlightRequests}`);
        }

        this.log("APP_HANDLER", `Menutup database connection pool secara aman.`);
        this.log("APP_HANDLER", `Aplikasi keluar secara bersih dengan Exit Code 0.`);
        this.log("KUBELET_SIGNAL", `Kontainer dihapus dari cgroups dan namespace. 0 Connection Drop Tercapai!\n`);
    }
}

async function run() {
    const pod = new PodLifecycleSimulator("payment-api-7b89f");

    console.log("=== TAHAP 1: STARTUP PROBE PADA APLIKASI LAMBAT ===");
    await pod.runStartupProbe();

    console.log("=== TAHAP 2: READINESS PROBE & SERVICE TRAFFIC ENABLING ===");
    pod.dbConnected = true;
    pod.evaluateReadiness();

    console.log("=== TAHAP 3: TRANSIENT OUTAGE (DATABASE GANGGUAN 5 DETIK) ===");
    console.log("Skenario: Database PostgreSQL sempat hang/restart.");
    pod.dbConnected = false;
    pod.evaluateReadiness(); // Should remove from endpoints without restarting!

    console.log("Skenario: Database PostgreSQL kembali normal.");
    pod.dbConnected = true;
    pod.evaluateReadiness(); // Re-adds to endpoints!

    console.log("=== TAHAP 4: MEMORY DEADLOCK & LIVENESS PROBE RESTART ===");
    console.log("Skenario: Bug di thread pool memicu deadlock permanen.");
    pod.isDeadlocked = true;
    pod.evaluateLiveness(); // Fail 1
    pod.evaluateLiveness(); // Fail 2
    pod.evaluateLiveness(); // Fail 3 -> Triggers Restart!

    // Step 5: Graceful Termination
    await pod.terminateGracefully();

    console.log("=== REKOMENDASI BEST PRACTICE ===");
    console.log("1. Selalu pasang startupProbe jika bootstrap aplikasi > 15 detik.");
    console.log("2. Jangan gunakan livenessProbe untuk cek dependensi eksternal (gunakan readiness).");
    console.log("3. Pasang 'preStop: sleep 5' untuk menjamin nol HTTP 502 saat rolling update.");
}

run().catch(console.error);
