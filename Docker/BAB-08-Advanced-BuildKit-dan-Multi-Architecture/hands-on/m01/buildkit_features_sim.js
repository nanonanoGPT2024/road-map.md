/**
 * hands-on/m01/buildkit_features_sim.js
 * 
 * Simulasi Engine BuildKit:
 * 1. LLB DAG (Directed Acyclic Graph) Parallel Execution.
 * 2. RUN --mount=type=cache (Persistent Package Manager Cache).
 * 3. RUN --mount=type=secret (Ephemeral Secret Injection without Layer Leakage).
 * 4. Verification: Inspecting Image Layer History to prove secret immunity.
 */

const crypto = require('crypto');

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

console.log("================================================================================");
console.log("             BUILDKIT ENGINE & SECURE MOUNT SIMULATOR v2.4                      ");
console.log("================================================================================\n");

class BuildKitSimulator {
    constructor() {
        this.cacheStorage = new Map(); // Simulates host buildkit cache volume
        this.imageLayers = [];
        this.buildLogs = [];
    }

    log(stage, message) {
        const timestamp = new Date().toISOString().substring(11, 19);
        console.log(`[${timestamp}] [Stage: ${stage.padEnd(12)}] ${message}`);
    }

    // Step 1: Parallel LLB Step Execution
    async runLLBStep(id, command, dependencies = [], durationMs = 300) {
        this.log(id, `Analyzing LLB node. Dependencies: [${dependencies.join(', ') || 'None'}]`);
        await sleep(durationMs);
        const digest = crypto.createHash('sha256').update(command + Date.now()).digest('hex').substring(0, 12);
        this.log(id, `Completed node "${command}" -> Output Digest: sha256:${digest}`);
        return digest;
    }

    // Step 2: Cache Mount Execution
    async runWithCacheMount(cacheKey, packageList) {
        this.log("CACHE_MOUNT", `RUN --mount=type=cache,target=/root/.npm,id=npm-cache npm install`);
        const cachedPackages = this.cacheStorage.get(cacheKey) || new Set();
        let downloadedCount = 0;
        let cachedCount = 0;

        for (const pkg of packageList) {
            if (cachedPackages.has(pkg)) {
                cachedCount++;
                this.log("CACHE_MOUNT", `  [HIT]  Using cached tarball for "${pkg}" (0.2ms)`);
            } else {
                downloadedCount++;
                this.log("CACHE_MOUNT", `  [MISS] Fetching "${pkg}" from registry & populating cache...`);
                await sleep(150);
                cachedPackages.add(pkg);
            }
        }
        this.cacheStorage.set(cacheKey, cachedPackages);
        this.log("CACHE_MOUNT", `Package install summary: ${cachedCount} cache hits, ${downloadedCount} downloaded.\n`);
    }

    // Step 3: Secret Mount vs Insecure ARG/ENV Comparison
    async runWithSecretMount(secretId, secretValue, curlEndpoint) {
        this.log("SECRET_MOUNT", `RUN --mount=type=secret,id=${secretId},target=/run/secrets/${secretId} curl -H "Auth: \$(cat /run/secrets/${secretId})" ${curlEndpoint}`);
        this.log("SECRET_MOUNT", `Mounting ephemeral tmpfs secret file at /run/secrets/${secretId}...`);
        
        // Emulate executing curl with authorization
        await sleep(200);
        const secretMasked = secretValue.substring(0, 3) + "****************" + secretValue.substring(secretValue.length - 3);
        this.log("SECRET_MOUNT", `Authentication successful using secret token: ${secretMasked}`);
        this.log("SECRET_MOUNT", `Process finished. Unmounting tmpfs /run/secrets/${secretId}.`);
        
        // Create an immutable layer
        const layerDigest = crypto.createHash('sha256').update("downloaded-private-package").digest('hex').substring(0, 16);
        this.imageLayers.push({
            instruction: `RUN --mount=type=secret,id=${secretId} curl private-artifactory`,
            layerId: `sha256:${layerDigest}`,
            storedData: "unpacked private npm bundle (no token saved)",
            containsSecret: false
        });
        this.log("SECRET_MOUNT", `Layer committed: sha256:${layerDigest} (Size: 4.8MB)\n`);
    }

    // Step 4: Compare with Insecure ARG
    async runInsecureArgBuild(secretValue) {
        this.log("INSECURE_ARG", `ARG GITHUB_TOKEN=${secretValue} (DEPRECATED & INSECURE)`);
        this.log("INSECURE_ARG", `RUN git clone https://\${GITHUB_TOKEN}@github.com/internal/lib.git`);
        await sleep(200);
        
        const layerDigest = crypto.createHash('sha256').update(secretValue).digest('hex').substring(0, 16);
        this.imageLayers.push({
            instruction: `ARG GITHUB_TOKEN=${secretValue} | RUN git clone ...`,
            layerId: `sha256:${layerDigest}`,
            storedData: `git checkout files containing token: "${secretValue}" in environment metadata`,
            containsSecret: true
        });
        this.log("INSECURE_ARG", `[CRITICAL ALERT] Token baked directly into image metadata & layer history!\n`);
    }

    // Verification & Security Audit
    auditImageLayers() {
        console.log("================================================================================");
        console.log("               DOCKER IMAGE LAYER & HISTORY SECURITY AUDIT                      ");
        console.log("================================================================================");
        console.log(String("Layer ID").padEnd(20) + String("Instruction / Mount Type").padEnd(42) + "Leak Status");
        console.log("--------------------------------------------------------------------------------");
        for (const layer of this.imageLayers) {
            const statusStr = layer.containsSecret ? "[LEAK DETECTED!]" : "[CLEAN / SECURE]";
            console.log(layer.layerId.padEnd(20) + layer.instruction.substring(0, 40).padEnd(42) + statusStr);
        }
        console.log("--------------------------------------------------------------------------------\n");
    }
}

async function main() {
    const sim = new BuildKitSimulator();

    console.log("=== SCENARIO 1: PARALLEL LLB GRAPH EXECUTION ===");
    console.log("BuildKit mendeteksi bahwa Frontend & Backend assets tidak saling bergantung.");
    console.log("Keduanya akan dieksekusi secara konkuren paralel, memangkas waktu build 50%!\n");

    const startTime = Date.now();
    await Promise.all([
        sim.runLLBStep("FE_BUILD", "RUN npm run build:frontend", [], 400),
        sim.runLLBStep("BE_BUILD", "RUN go build -o /bin/api ./cmd/api", [], 400),
        sim.runLLBStep("LINTING", "RUN golangci-lint run", [], 300)
    ]);
    console.log(`Parallel execution complete in ${Date.now() - startTime}ms (Sequential would take ~1100ms).\n`);

    console.log("=== SCENARIO 2: CACHE MOUNT RE-BUILD TEST ===");
    const packages = ["express", "dotenv", "pg", "jsonwebtoken", "zod"];
    console.log("[Build 1] Cold cache run:");
    await sim.runWithCacheMount("npm-cache-id", packages);

    console.log("[Build 2] Re-building after minor code change (Cache Mount Preserved):");
    await sim.runWithCacheMount("npm-cache-id", packages);

    console.log("=== SCENARIO 3: SECRET MOUNT VS INSECURE ARG/ENV ===");
    const fakeToken = "ghp_ProdKeySecureSecretVault2026";
    await sim.runWithSecretMount("github_token", fakeToken, "https://npm.pkg.github.com/internal-module");
    await sim.runInsecureArgBuild("ghp_InsecureLeakedToken999");

    sim.auditImageLayers();

    console.log("=== KESIMPULAN & REKOMENDASI BUILDKIT ===");
    console.log("1. Gunakan 'DOCKER_BUILDKIT=1' atau Docker Engine 23+ (BuildKit default).");
    console.log("2. Gunakan '--mount=type=cache' untuk dependencies package manager.");
    console.log("3. Gunakan '--mount=type=secret,id=...' untuk credentials API, token Git, dan private keys.");
    console.log("4. HINDARI 'ARG' atau 'ENV' untuk menyimpan tokens/passwords karena pasti terbaca di 'docker history'.\n");
}

main().catch(err => {
    console.error("Simulation failed:", err);
    process.exit(1);
});
