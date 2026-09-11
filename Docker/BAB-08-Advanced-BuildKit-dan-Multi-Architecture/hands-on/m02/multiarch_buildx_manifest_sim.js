/**
 * hands-on/m02/multiarch_buildx_manifest_sim.js
 * 
 * Simulasi Docker Buildx Multi-Architecture Build & OCI Manifest List:
 * 1. Buildx Builder Instance Setup & Platform Capability Probing.
 * 2. Multi-Platform Build Pipeline (AMD64 & ARM64).
 * 3. OCI Image Index / Manifest List Assembly & Validation.
 * 4. Client Pull Resolution Simulation (Host CPU detection & layer selection).
 * 5. CLI Simulator: "docker buildx imagetools inspect".
 */

const crypto = require('crypto');

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

console.log("================================================================================");
console.log("          DOCKER BUILDX MULTI-ARCHITECTURE MANIFEST SIMULATOR                   ");
console.log("================================================================================\n");

class MultiArchRegistrySimulator {
    constructor() {
        this.manifestStorage = new Map(); // Store manifests and index
    }

    log(component, msg) {
        const ts = new Date().toISOString().substring(11, 19);
        console.log(`[${ts}] [${component.padEnd(14)}] ${msg}`);
    }

    // Generate pseudo OCI digest
    generateDigest(content) {
        const hash = crypto.createHash('sha256').update(JSON.stringify(content)).digest('hex');
        return `sha256:${hash}`;
    }

    // Step 1: Simulate Buildx Compiling for a specific platform
    async compilePlatform(imageTag, platform, compilerMode = "cross-compile") {
        this.log("BUILDX_ENGINE", `Building layer for platform: ${platform} using [${compilerMode}]`);
        await sleep(250);

        const binaryContent = `executable-binary-payload-for-${platform}-${Date.now()}`;
        const layerDigest = this.generateDigest(binaryContent);

        const manifest = {
            schemaVersion: 2,
            mediaType: "application/vnd.oci.image.manifest.v1+json",
            config: {
                mediaType: "application/vnd.oci.image.config.v1+json",
                size: 1450,
                digest: this.generateDigest(`config-${platform}`)
            },
            layers: [
                {
                    mediaType: "application/vnd.oci.image.layer.v1.tar+gzip",
                    size: platform === "linux/arm64" ? 14200000 : 15800000,
                    digest: layerDigest
                }
            ],
            annotations: {
                "org.opencontainers.image.architecture": platform.split('/')[1],
                "org.opencontainers.image.os": platform.split('/')[0]
            }
        };

        const manifestDigest = this.generateDigest(manifest);
        this.manifestStorage.set(manifestDigest, manifest);
        this.log("BUILDX_ENGINE", `  -> Platform ${platform} compiled! Manifest Digest: ${manifestDigest.substring(0, 19)}...`);
        
        return {
            platform: {
                architecture: platform.split('/')[1],
                os: platform.split('/')[0]
            },
            size: manifest.layers[0].size + manifest.config.size,
            digest: manifestDigest
        };
    }

    // Step 2: Assemble OCI Manifest List (Image Index)
    assembleManifestList(imageTag, platformManifests) {
        this.log("MANIFEST_TOOL", `Creating OCI Image Index (Manifest List) for tag: ${imageTag}`);
        
        const indexDocument = {
            schemaVersion: 2,
            mediaType: "application/vnd.oci.image.index.v1+json",
            manifests: platformManifests
        };

        const indexDigest = this.generateDigest(indexDocument);
        this.manifestStorage.set(imageTag, {
            indexDigest,
            document: indexDocument
        });

        this.log("MANIFEST_TOOL", `Pushed Manifest List to Registry! Root Index Digest: ${indexDigest.substring(0, 19)}...\n`);
        return indexDigest;
    }

    // Step 3: Inspect Manifest List (mimicking "docker buildx imagetools inspect")
    inspectImage(imageTag) {
        console.log(`\n$ docker buildx imagetools inspect ${imageTag}`);
        console.log("--------------------------------------------------------------------------------");
        const entry = this.manifestStorage.get(imageTag);
        if (!entry) {
            console.log(`Error: Image ${imageTag} not found in registry!`);
            return;
        }

        console.log(`Name:      ${imageTag}`);
        console.log(`MediaType: ${entry.document.mediaType}`);
        console.log(`Digest:    ${entry.indexDigest}`);
        console.log(`\nManifests:`);
        entry.document.manifests.forEach((m, idx) => {
            const sizeMb = (m.size / (1024 * 1024)).toFixed(2);
            console.log(`  [${idx + 1}] Platform:     ${m.platform.os}/${m.platform.architecture}`);
            console.log(`      Digest:       ${m.digest}`);
            console.log(`      Size:         ${sizeMb} MB`);
        });
        console.log("--------------------------------------------------------------------------------\n");
    }

    // Step 4: Simulate Client Pull & Architecture Auto-Resolution
    simulateClientPull(imageTag, clientArch, clientOS = "linux") {
        this.log("DOCKER_PULL", `Host [${clientOS}/${clientArch}] executing: docker pull ${imageTag}`);
        const entry = this.manifestStorage.get(imageTag);
        if (!entry) {
            this.log("DOCKER_PULL", `[ERROR] Tag ${imageTag} not found.`);
            return;
        }

        const match = entry.document.manifests.find(
            m => m.platform.os === clientOS && m.platform.architecture === clientArch
        );

        if (match) {
            const layerManifest = this.manifestStorage.get(match.digest);
            this.log("DOCKER_PULL", `  [MATCH FOUND] Resolved to platform: ${match.platform.os}/${match.platform.architecture}`);
            this.log("DOCKER_PULL", `  Downloading binary layer: ${layerManifest.layers[0].digest.substring(0, 19)}... (${(match.size / (1024 * 1024)).toFixed(2)} MB)`);
            this.log("DOCKER_PULL", `  [SUCCESS] Container can start natively without emulation overhead!\n`);
        } else {
            this.log("DOCKER_PULL", `  [INCOMPATIBLE] No binary available for ${clientOS}/${clientArch}!`);
            this.log("DOCKER_PULL", `  [CRASH SIMULATION] standard_init_linux.go: exec format error!\n`);
        }
    }
}

async function run() {
    const registry = new MultiArchRegistrySimulator();
    const appTag = "docker.io/myorg/cloud-microservice:v2.0.0";

    console.log("=== TAHAP 1: BUILD PLATFORM BINER MENGGUNAKAN BUILDX ===");
    const platforms = ["linux/amd64", "linux/arm64"];
    const compiledManifests = [];

    for (const p of platforms) {
        const manifestMeta = await registry.compilePlatform(appTag, p, "native-cross-compile");
        compiledManifests.push(manifestMeta);
    }

    console.log("=== TAHAP 2: PEMBUATAN & PUBLIKASI OCI MANIFEST LIST ===");
    registry.assembleManifestList(appTag, compiledManifests);

    console.log("=== TAHAP 3: INSPEKSI METADATA DENGAN DOCKER BUILDX IMAGETOOLS ===");
    registry.inspectImage(appTag);

    console.log("=== TAHAP 4: SIMULASI CLIENT PULL PADA BERBAGAI HOST CPU ===");
    // Host 1: Standard Intel/AMD Cloud Server
    registry.simulateClientPull(appTag, "amd64", "linux");

    // Host 2: Apple Silicon / AWS Graviton
    registry.simulateClientPull(appTag, "arm64", "linux");

    // Host 3: Unsupported architecture (e.g. mainframe s390x)
    registry.simulateClientPull(appTag, "s390x", "linux");

    console.log("=== RANGKUMAN PENERAPAN PRODUCTION ===");
    console.log("1. Multi-Arch Manifest List mengeliminasi fragmentasi tag ('-arm64', '-amd64').");
    console.log("2. Performa container berjalan 100% native di AWS Graviton dan Intel Xeon.");
    console.log("3. Gunakan 'docker buildx build --platform linux/amd64,linux/arm64 -t <tag> --push .' pada CI/CD.");
}

run().catch(console.error);
