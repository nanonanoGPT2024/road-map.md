/**
 * hands-on/m02/systemd_watchtower_lifecycle_sim.js
 * 
 * Simulasi Produksi Single-Host Docker:
 * 1. Linux Systemd Unit Dependency & Boot Superintendant.
 * 2. Watchtower Continuous Delivery Polling & Graceful Container Replacement.
 * 3. Automated Garbage Collection / Docker System Prune Scheduler (168h filter).
 * 4. Disk Reclaim Audit & Space Optimization Metrics.
 */

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

console.log("================================================================================");
console.log("    PRODUCTION HOST SUPERINTENDANT (SYSTEMD, WATCHTOWER, PRUNE) SIMULATOR       ");
console.log("================================================================================\n");

class ProductionHostSimulator {
    constructor() {
        this.services = new Map();
        this.containers = [];
        this.diskBloatMb = 45000; // 45 GB total docker footprint
    }

    log(subsystem, msg) {
        const ts = new Date().toISOString().substring(11, 19);
        console.log(`[${ts}] [${subsystem.padEnd(16)}] ${msg}`);
    }

    // Step 1: Systemd Boot Sequence Simulator
    async simulateHostBoot() {
        console.log("=== TAHAP 1: SIMULASI SYSTEMD OS BOOT & DEPENDENCY RESOLUTION ===");
        this.log("SYSTEMD_INIT", "Kernel boot completed. Target: multi-user.target reached.");
        this.log("SYSTEMD_INIT", "Waiting for network-online.target... OK.");
        this.log("SYSTEMD_INIT", "Starting docker.service (Docker Daemon)... OK.");
        await sleep(200);

        this.log("SYSTEMD_UNIT", "Triggering /etc/systemd/system/production-stack.service (ExecStart)...");
        this.log("DOCKER_COMPOSE", "Executing: docker compose -f /opt/app/docker-compose.yml up -d");
        
        // Spawn production containers
        this.containers.push({
            id: "c_api_01",
            name: "fintech-api",
            imageTag: "ghcr.io/myorg/api:v1.0.0",
            imageDigest: "sha256:1111aaaa",
            status: "running",
            watchtowerEnabled: true
        });

        this.containers.push({
            id: "c_db_01",
            name: "postgres-db",
            imageTag: "postgres:16-alpine",
            imageDigest: "sha256:2222bbbb",
            status: "running",
            watchtowerEnabled: false // Excluded from auto-update!
        });

        this.log("DOCKER_COMPOSE", "Container fintech-api [healthy] (Port: 8080)");
        this.log("DOCKER_COMPOSE", "Container postgres-db [healthy] (Port: 5432)");
        this.log("SYSTEMD_UNIT", "Service production-stack.service entered state ACTIVE (running).\n");
    }

    // Step 2: Watchtower CD Polling Simulator
    async runWatchtowerPoll(remoteRegistryUpdates) {
        console.log("=== TAHAP 2: WATCHTOWER REGISTRY POLLING & SELECTIVE ROLLING UPDATE ===");
        this.log("WATCHTOWER", "Checking for container image updates across registry...");

        for (const container of this.containers) {
            this.log("WATCHTOWER", `Evaluating container: "${container.name}"`);
            if (!container.watchtowerEnabled) {
                this.log("WATCHTOWER", `  [SKIPPED] Label 'com.centurylinklabs.watchtower.enable' is FALSE. Database auto-update protected!`);
                continue;
            }

            const latestRemoteDigest = remoteRegistryUpdates[container.imageTag.split(':')[0]];
            if (latestRemoteDigest && latestRemoteDigest !== container.imageDigest) {
                this.log("WATCHTOWER", `  [UPDATE DETECTED] New digest found in registry!`);
                this.log("WATCHTOWER", `  Current : ${container.imageDigest} -> Remote : ${latestRemoteDigest}`);
                
                // Rolling update simulation
                this.log("WATCHTOWER", `  Graceful shutdown: Sending SIGTERM to "${container.name}" (Timeout: 30s)...`);
                await sleep(250);
                this.log("WATCHTOWER", `  Container stopped cleanly.`);
                this.log("WATCHTOWER", `  Deploying new container with image digest: ${latestRemoteDigest}...`);
                container.imageDigest = latestRemoteDigest;
                container.imageTag = container.imageTag.split(':')[0] + ":v1.1.0";
                this.log("WATCHTOWER", `  [SUCCESS] Container "${container.name}" restarted successfully with new version!`);
                this.log("WATCHTOWER", `  Old image layers marked as dangling.\n`);
            } else {
                this.log("WATCHTOWER", `  [UP TO DATE] Running image digest matches remote registry.\n`);
            }
        }
    }

    // Step 3: Automated Pruning Simulator (Systemd Timer)
    simulateAutomatedPruning() {
        console.log("=== TAHAP 3: AUTOMATED DISK HYGIENE (DOCKER SYSTEM PRUNE --FILTER) ===");
        this.log("SYSTEMD_TIMER", "Weekly timer 'docker-prune.timer' triggered.");
        this.log("PRUNE_ENGINE", `Initial Docker Disk Utilization: ${(this.diskBloatMb / 1024).toFixed(2)} GB`);
        this.log("PRUNE_ENGINE", `Running: docker system prune -af --filter "until=168h"`);

        const reclaimedMb = 28500; // 28.5 GB pruned
        this.diskBloatMb -= reclaimedMb;

        console.log("--------------------------------------------------------------------------------");
        console.log("Deleted Items Summary:");
        console.log("  - 14 Dangling/Untagged image layers (older than 7 days)");
        console.log("  - 8 Exited batch-job and CI test containers");
        console.log("  - 18.2 GB of unused BuildKit build cache");
        console.log("--------------------------------------------------------------------------------");
        this.log("PRUNE_ENGINE", `Total space reclaimed: ${(reclaimedMb / 1024).toFixed(2)} GB`);
        this.log("PRUNE_ENGINE", `Final Docker Disk Utilization: ${(this.diskBloatMb / 1024).toFixed(2)} GB (Clean and safe!)\n`);
    }
}

async function run() {
    const host = new ProductionHostSimulator();

    // 1. Boot OS and start Systemd service
    await host.simulateHostBoot();

    // 2. Simulate Watchtower detecting a new release on API but not DB
    const remoteUpdates = {
        "ghcr.io/myorg/api": "sha256:9999cccc" // New build released by CI/CD!
    };
    await host.runWatchtowerPoll(remoteUpdates);

    // 3. Trigger weekly pruning timer
    host.simulateAutomatedPruning();

    console.log("=== PRODUCTION READINESS CHECKLIST ===");
    console.log("✅ Systemd Unit: Survives server reboots without human intervention.");
    console.log("✅ Watchtower Selective: Updates microservices automatically while shielding DB.");
    console.log("✅ Automated Prune: Prevents 'no space left on device' emergency outages.");
}

run().catch(console.error);
