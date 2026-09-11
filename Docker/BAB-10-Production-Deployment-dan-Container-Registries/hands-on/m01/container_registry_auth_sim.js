/**
 * hands-on/m01/container_registry_auth_sim.js
 * 
 * Simulasi OCI Container Registry Architecture, Token Auth, & Tag Immutability:
 * 1. OCI Distribution Protocol (401 Challenge -> JWT Token Issuance).
 * 2. Blob Content-Addressable Storage & Deduplication Engine.
 * 3. Tag Immutability Policy Enforcement (Blocking overwriting existing tags).
 * 4. Docker Credential Helper vs Plaintext Storage Security Audit.
 * 5. Production Triple-Tagging Pipeline (SemVer, Git SHA, Floating Track).
 */

const crypto = require('crypto');

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

console.log("================================================================================");
console.log("       OCI CONTAINER REGISTRY & TAG IMMUTABILITY SIMULATOR v2.2                 ");
console.log("================================================================================\n");

class OciRegistryServer {
    constructor() {
        this.blobs = new Map(); // SHA256 -> binary data
        this.manifests = new Map(); // "repo:tag" -> manifest document
        this.immutableTags = new Set(); // Tags protected from overwrite
        this.activeTokens = new Set();
    }

    log(section, msg) {
        const ts = new Date().toISOString().substring(11, 19);
        console.log(`[${ts}] [${section.padEnd(16)}] ${msg}`);
    }

    // Step 1: Token Authentication
    authenticate(username, password) {
        this.log("REGISTRY_AUTH", `Evaluating credentials for user: "${username}"`);
        if (username === "devops-robot" && password === "SuperSecretToken2026") {
            const token = "jwt_token_" + crypto.randomBytes(16).toString('hex');
            this.activeTokens.add(token);
            this.log("REGISTRY_AUTH", `  [SUCCESS] 200 OK -> Issued Bearer JWT Token: ${token.substring(0, 24)}...`);
            return token;
        }
        this.log("REGISTRY_AUTH", `  [FAILED] 401 Unauthorized -> Invalid credentials!`);
        return null;
    }

    // Step 2: Check Blob Existence (Deduplication)
    hasBlob(digest) {
        return this.blobs.has(digest);
    }

    // Upload Blob
    uploadBlob(token, data) {
        if (!this.activeTokens.has(token)) throw new Error("401 Unauthorized: Invalid Token");
        const digest = "sha256:" + crypto.createHash('sha256').update(data).digest('hex');
        if (this.hasBlob(digest)) {
            this.log("BLOB_STORE", `  [LAYER DEDUPLICATION] Layer ${digest.substring(0, 19)} already exists in registry. Skipping upload! (0ms)`);
        } else {
            this.blobs.set(digest, data);
            this.log("BLOB_STORE", `  [UPLOADED] New Layer ${digest.substring(0, 19)} stored (${Buffer.byteLength(data)} bytes).`);
        }
        return digest;
    }

    // Step 3: Put Manifest with Immutability Gate
    putManifest(token, repo, tag, manifestPayload) {
        if (!this.activeTokens.has(token)) throw new Error("401 Unauthorized: Invalid Token");
        const key = `${repo}:${tag}`;

        // Tag Immutability Enforcement
        if (this.immutableTags.has(key)) {
            this.log("IMMUTABILITY_GATE", `[CRITICAL 412 PRECONDITION FAILED] Tag "${key}" is IMMUTABLE!`);
            this.log("IMMUTABILITY_GATE", `  Supply Chain Security Policy: Overwriting existing release tags is forbidden!`);
            return { status: 412, message: "Tag is immutable and cannot be overwritten." };
        }

        this.manifests.set(key, manifestPayload);

        // Auto-lock SemVer tags (e.g. v1.0.0) as immutable
        if (/^v\d+\.\d+\.\d+$/.test(tag)) {
            this.immutableTags.add(key);
            this.log("IMMUTABILITY_GATE", `  [LOCKED] Tag "${key}" identified as SemVer release. Policy locked to IMMUTABLE.`);
        }

        this.log("MANIFEST_STORE", `201 Created -> Successfully registered manifest for "${key}"`);
        return { status: 201, message: "Created" };
    }
}

// Client Workflow Simulator
async function run() {
    const registry = new OciRegistryServer();

    console.log("=== TAHAP 1: AUTENTIKASI OAUTH2 / BEARER TOKEN ===");
    // Attempt with invalid password
    registry.authenticate("devops-robot", "wrong_password");
    // Attempt with valid token
    const token = registry.authenticate("devops-robot", "SuperSecretToken2026");
    console.log("");

    console.log("=== TAHAP 2: LAYER DEDUPLICATION TEST ===");
    const baseLayerData = "alpine-linux-3.19-rootfs-content";
    const appLayerData1 = "payment-api-binary-v1.0.0";
    const appLayerData2 = "payment-api-binary-v1.0.1";

    console.log("[Build & Push Image v1.0.0]");
    const baseDigest = registry.uploadBlob(token, baseLayerData);
    const app1Digest = registry.uploadBlob(token, appLayerData1);

    console.log("\n[Build & Push Image v1.0.1 (Sharing same base layer)]");
    registry.uploadBlob(token, baseLayerData); // Proves deduplication!
    const app2Digest = registry.uploadBlob(token, appLayerData2);
    console.log("");

    console.log("=== TAHAP 3: PRODUCTION TRIPLE-TAGGING PIPELINE ===");
    const repo = "fintech/payment-gateway";
    const semverTag = "v1.0.0";
    const gitShaTag = "sha-a8f3b2c";
    const floatingTag = "v1";

    const manifestV1 = {
        schemaVersion: 2,
        layers: [baseDigest, app1Digest]
    };

    console.log(`Publishing tag 1 (SemVer): ${repo}:${semverTag}`);
    registry.putManifest(token, repo, semverTag, manifestV1);

    console.log(`Publishing tag 2 (Git SHA): ${repo}:${gitShaTag}`);
    registry.putManifest(token, repo, gitShaTag, manifestV1);

    console.log(`Publishing tag 3 (Floating): ${repo}:${floatingTag}`);
    registry.putManifest(token, repo, floatingTag, manifestV1);
    console.log("");

    console.log("=== TAHAP 4: PENGUJIAN TAG IMMUTABILITY PROTECTION ===");
    console.log("Skenario: Developer sengaja/tidak sengaja mencoba menimpa tag v1.0.0 yang sudah dirilis:");
    const maliciousManifest = {
        schemaVersion: 2,
        layers: [baseDigest, app2Digest] // altered content
    };

    const result = registry.putManifest(token, repo, semverTag, maliciousManifest);
    console.log(`Status Hasil Push: HTTP ${result.status} (${result.message})\n`);

    console.log("=== TAHAP 5: CREDENTIAL HELPER VS DOCKER CONFIG AUDIT ===");
    console.log("Audit ~/.docker/config.json:");
    console.log("❌ BAD  : {\"auths\": {\"ghcr.io\": {\"auth\": \"ZGV2b3Bz...\"}}} -> Plaintext exposed!");
    console.log("✅ GOOD : {\"credsStore\": \"wincred\"} (atau \"secretservice\" / \"osxkeychain\") -> Protected by OS Vault.\n");
}

run().catch(console.error);
