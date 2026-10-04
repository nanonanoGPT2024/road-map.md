/**
 * hands-on/m02/container_resource_profiler.js
 * 
 * Simulasi Container Resource Profiling & Exit Code Diagnostics:
 * 1. cAdvisor / docker stats metrics engine (CPU, Memory, Network I/O).
 * 2. Cgroup Memory Threshold & Linux OOM Killer Simulation (Exit Code 137).
 * 3. Exit Code Matrix Diagnosis (Codes 0, 1, 126, 127, 137, 143).
 * 4. Forensic Troubleshooting Automation for Container Crashes.
 */

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

console.log("================================================================================");
console.log("         CONTAINER PERFORMANCE PROFILER & OOM DIAGNOSTIC TOOL                   ");
console.log("================================================================================\n");

class ContainerResourceProfiler {
    constructor() {
        this.containers = new Map();
    }

    registerContainer(id, name, memLimitMb, cpuShares = 1024) {
        this.containers.set(id, {
            id,
            name,
            memLimitMb,
            currentMemMb: 20,
            cpuPercent: 1.5,
            netIoKb: 120,
            status: "running",
            exitCode: null,
            oomKilled: false,
            logs: []
        });
    }

    log(id, msg) {
        const c = this.containers.get(id);
        if (c) c.logs.push(`[${new Date().toISOString().substring(11, 19)}] ${msg}`);
    }

    // Step 1: Simulate memory spike leading to OOM
    async simulateMemoryLeak(id, leakStepMb = 30, iterations = 6) {
        const c = this.containers.get(id);
        console.log(`[SIMULASI MEMORY LEAK] Container "${c.name}" (Limit: ${c.memLimitMb} MB) mulai mengalami kebocoran memori...`);

        for (let i = 1; i <= iterations; i++) {
            await sleep(150);
            c.currentMemMb += leakStepMb;
            c.cpuPercent = Math.min(98.5, c.cpuPercent + 14.2);
            c.netIoKb += 450;
            const memPercent = ((c.currentMemMb / c.memLimitMb) * 100).toFixed(1);

            console.log(`  -> Iterasi ${i}: RAM: ${c.currentMemMb.toFixed(1)}MB / ${c.memLimitMb}MB (${memPercent}%) | CPU: ${c.cpuPercent.toFixed(1)}%`);

            if (c.currentMemMb >= c.memLimitMb) {
                console.log(`\n  [KERNEL ALERT] Cgroups v2 memory limit breached (${c.currentMemMb}MB >= ${c.memLimitMb}MB)!`);
                console.log(`  [OOM KILLER ACTIVATED] Linux Kernel invoker: sending SIGKILL (Signal 9) to PID 1!`);
                c.status = "exited";
                c.exitCode = 137; // 128 + 9
                c.oomKilled = true;
                this.log(id, "Fatal: Process terminated by kernel OOM-killer.");
                break;
            }
        }
        console.log("");
    }

    // Display "docker stats" view
    printDockerStats() {
        console.log("=== DOCKER STATS (SNAPSHOT) ===");
        console.log(String("CONTAINER ID").padEnd(15) + String("NAME").padEnd(20) + String("CPU %").padEnd(12) + String("MEM USAGE / LIMIT").padEnd(24) + String("MEM %").padEnd(10) + "STATUS");
        console.log("--------------------------------------------------------------------------------");
        for (const [id, c] of this.containers.entries()) {
            const memStr = `${c.currentMemMb.toFixed(1)}MiB / ${c.memLimitMb}MiB`;
            const memPerc = `${((c.currentMemMb / c.memLimitMb) * 100).toFixed(1)}%`;
            console.log(
                id.substring(0, 12).padEnd(15) +
                c.name.padEnd(20) +
                `${c.cpuPercent.toFixed(2)}%`.padEnd(12) +
                memStr.padEnd(24) +
                memPerc.padEnd(10) +
                c.status.toUpperCase()
            );
        }
        console.log("--------------------------------------------------------------------------------\n");
    }

    // Step 2: Exit Code Forensic Diagnostic Engine
    static diagnoseContainerCrash(containerMeta) {
        console.log(`[FORENSIC INSPECTION] Container: "${containerMeta.name}" (Exit Code: ${containerMeta.exitCode})`);
        console.log(`  State.OOMKilled : ${containerMeta.oomKilled}`);
        console.log(`  State.ExitCode  : ${containerMeta.exitCode}`);

        let diagnosis = "";
        let recommendation = "";

        switch (containerMeta.exitCode) {
            case 0:
                diagnosis = "Container selesai secara normal (Clean Shutdown).";
                recommendation = "Tidak ada tindakan yang diperlukan jika ini adalah batch job / migration task.";
                break;
            case 1:
                diagnosis = "Aplikasi melempar uncaught exception atau syntax runtime error.";
                recommendation = "Periksa log aplikasi ('docker logs <id>') untuk melihat stack trace error.";
                break;
            case 126:
                diagnosis = "Permission denied: Script entrypoint tidak memiliki izin eksekusi.";
                recommendation = "Tambahkan 'RUN chmod +x /path/entrypoint.sh' pada Dockerfile.";
                break;
            case 127:
                diagnosis = "Command not found: Executable path tidak ditemukan di dalam $PATH.";
                recommendation = "Periksa path binary pada instruksi ENTRYPOINT/CMD atau periksa shared library dependencies.";
                break;
            case 137:
                if (containerMeta.oomKilled) {
                    diagnosis = "CRITICAL: Container terbunuh oleh Linux OOM (Out Of Memory) Killer!";
                    recommendation = "Tingkatkan batasan memori container cgroups atau batasi heap runtime (cth: --max-old-space-size di Node.js / -Xmx di Java).";
                } else {
                    diagnosis = "Container menerima sinyal SIGKILL (docker kill atau docker stop timeout 10 detik).";
                    recommendation = "Periksa apakah proses aplikasi menolak sinyal SIGTERM atau membutuhkan waktu shutdown lebih lama.";
                }
                break;
            case 143:
                diagnosis = "Graceful termination: Container dihentikan via SIGTERM (docker stop normal).";
                recommendation = "Perilaku normal selama rolling update atau orchestrator maintenance.";
                break;
            default:
                diagnosis = `Exit code non-standar: ${containerMeta.exitCode}`;
                recommendation = "Konsultasikan dokumentasi aplikasi.";
        }

        console.log(`  Diagnosa        : ${diagnosis}`);
        console.log(`  Rekomendasi     : ${recommendation}\n`);
    }
}

async function run() {
    const profiler = new ContainerResourceProfiler();

    profiler.registerContainer("c1a2b3c4d5e6", "auth-api", 512);
    profiler.registerContainer("f7g8h9i0j1k2", "report-worker", 128); // Low memory limit
    profiler.registerContainer("k3l4m5n6o7p8", "redis-cache", 256);

    // Initial stats
    profiler.printDockerStats();

    // Trigger OOM on report-worker
    await profiler.simulateMemoryLeak("f7g8h9i0j1k2", 35, 5);

    // Updated stats showing crashed container
    profiler.printDockerStats();

    console.log("=== PENGUJIAN FORENSIK BERBAGAI SKENARIO EXIT CODE ===");
    
    // Scenario 1: The OOM container we just killed
    const oomContainer = profiler.containers.get("f7g8h9i0j1k2");
    ContainerResourceProfiler.diagnoseContainerCrash(oomContainer);

    // Scenario 2: Command Not Found (127)
    ContainerResourceProfiler.diagnoseContainerCrash({
        name: "python-batch-job",
        exitCode: 127,
        oomKilled: false
    });

    // Scenario 3: Permission Denied (126)
    ContainerResourceProfiler.diagnoseContainerCrash({
        name: "entrypoint-runner",
        exitCode: 126,
        oomKilled: false
    });

    // Scenario 4: Unhandled Exception (1)
    ContainerResourceProfiler.diagnoseContainerCrash({
        name: "payment-checkout",
        exitCode: 1,
        oomKilled: false
    });

    console.log("=== BEST PRACTICE CHECKLIST PRODUKSI ===");
    console.log("1. Pantau metrik cgroups via cAdvisor + Prometheus secara kontinu.");
    console.log("2. Jangan biarkan limit memory container sama persis dengan heap limit aplikasi.");
    console.log("3. Gunakan 'docker inspect <name> --format {{.State.OOMKilled}}' saat investigasi insiden.");
}

run().catch(console.error);
