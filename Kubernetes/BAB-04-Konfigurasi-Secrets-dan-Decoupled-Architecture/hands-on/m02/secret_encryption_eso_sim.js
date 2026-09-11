/**
 * hands-on/m02/secret_encryption_eso_sim.js
 * 
 * Simulasi Keamanan Kubernetes Secrets & External Secrets Operator (ESO):
 * 1. Base64 vs Real Encryption at Rest (AES-256-GCM etcd storage simulation).
 * 2. External Secrets Operator Sync Engine (Cloud Vault -> Native K8s Secret).
 * 3. Centralized Secret Rotation Propagation.
 * 4. File Permission Security Audit (defaultMode: 0400 vs 0644).
 */

const crypto = require('crypto');

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

console.log("================================================================================");
console.log("       KUBERNETES SECRETS, ENCRYPTION AT REST, & ESO SIMULATOR v2.4             ");
console.log("================================================================================\n");

// Step 1: Base64 vs AES-256-GCM Simulation
class SecretEncryptionSimulator {
    static testBase64Vulnerability(secretRaw) {
        console.log("=== BAGIAN 1: PEMBUKTIAN KERENTANAN BASE64 ===");
        const encoded = Buffer.from(secretRaw).toString('base64');
        console.log(`Raw Secret         : "${secretRaw}"`);
        console.log(`Base64 Encoded     : "${encoded}"`);
        
        // Decoding without any key
        const decoded = Buffer.from(encoded, 'base64').toString('utf8');
        console.log(`Decoded tanpa Kunci: "${decoded}"`);
        console.log(`⚠️  KESIMPULAN: Base64 BUKAN ENKRIPSI! Siapa pun bisa membaca data ini secara instan!\n`);
    }

    static encryptForEtcd(secretPayload, masterKeyHex) {
        console.log("=== BAGIAN 2: ENCRYPTION AT REST DENGAN AES-256-GCM (ETCD) ===");
        const iv = crypto.randomBytes(12);
        const cipher = crypto.createCipheriv('aes-256-gcm', Buffer.from(masterKeyHex, 'hex'), iv);
        
        let encrypted = cipher.update(secretPayload, 'utf8', 'hex');
        encrypted += cipher.final('hex');
        const authTag = cipher.getAuthTag().toString('hex');

        const etcdStoredCiphertext = `k8s:enc:aescbc:v1:key1:${iv.toString('hex')}:${encrypted}:${authTag}`;
        console.log(`Disimpan ke database etcd di disk host:`);
        console.log(`  -> ${etcdStoredCiphertext}`);
        console.log(`🔒 Data 100% aman terenkripsi di level storage! Tanpa master key, data tidak bisa dibaca.\n`);
        return { etcdStoredCiphertext, iv, authTag };
    }
}

// Step 2: External Secrets Operator (ESO) Simulation
class ExternalSecretsOperatorSimulator {
    constructor() {
        this.cloudVault = new Map(); // Simulates AWS Secrets Manager / Vault
        this.k8sSecretsStore = new Map(); // Native Kubernetes Secrets in cluster
    }

    log(agent, msg) {
        const ts = new Date().toISOString().substring(11, 19);
        console.log(`[${ts}] [${agent.padEnd(16)}] ${msg}`);
    }

    // Set secret in cloud vault
    setCloudSecret(path, data) {
        this.cloudVault.set(path, { ...data, lastUpdated: new Date().toISOString() });
        this.log("CLOUD_VAULT", `Secret tersimpan di AWS Secrets Manager: "${path}"`);
    }

    // ESO Sync Reconciliation Loop
    syncExternalSecret(secretStoreName, externalSecretSpec) {
        this.log("ESO_OPERATOR", `Reconciling ExternalSecret: "${externalSecretSpec.name}" via SecretStore: "${secretStoreName}"`);
        
        const remoteData = this.cloudVault.get(externalSecretSpec.remoteKey);
        if (!remoteData) {
            this.log("ESO_OPERATOR", `  ❌ [SYNC FAILED] Remote secret "${externalSecretSpec.remoteKey}" tidak ditemukan di Vault!`);
            return;
        }

        // Convert to Native K8s Secret format
        const targetSecretName = externalSecretSpec.targetName;
        const nativeSecret = {
            apiVersion: "v1",
            kind: "Secret",
            metadata: {
                name: targetSecretName,
                namespace: externalSecretSpec.namespace,
                labels: { "app.kubernetes.io/managed-by": "external-secrets" }
            },
            type: "Opaque",
            data: {}
        };

        // Base64 encode fields for native K8s secret
        for (const [k, v] of Object.entries(remoteData)) {
            if (k !== "lastUpdated") {
                nativeSecret.data[k] = Buffer.from(String(v)).toString('base64');
            }
        }

        this.k8sSecretsStore.set(targetSecretName, nativeSecret);
        this.log("ESO_OPERATOR", `  ✅ [STATUS: SecretSynced] Native Kubernetes Secret "${targetSecretName}" berhasil dibuat/diperbarui!`);
        this.log("ESO_OPERATOR", `     Data keys: [${Object.keys(nativeSecret.data).join(', ')}]\n`);
    }
}

async function run() {
    // 1. Base64 vs Encryption Test
    const secretPassword = "SuperConfidentialBankToken987654";
    SecretEncryptionSimulator.testBase64Vulnerability(secretPassword);

    const masterKey = crypto.randomBytes(32).toString('hex');
    SecretEncryptionSimulator.encryptForEtcd(secretPassword, masterKey);

    // 2. External Secrets Operator (ESO) Test
    console.log("=== BAGIAN 3: SINKRONISASI EXTERNAL SECRETS OPERATOR (ESO) ===");
    const eso = new ExternalSecretsOperatorSimulator();

    // Inisialisasi secret di Vault
    eso.setCloudSecret("prod/fintech/database", {
        DB_USER: "fintech_admin",
        DB_PASS: "SecretPass2026_Initial"
    });

    const externalSecretSpec = {
        name: "payment-db-sync",
        namespace: "production",
        remoteKey: "prod/fintech/database",
        targetName: "payment-db-native-secret"
    };

    // Sinkronisasi Pertama
    eso.syncExternalSecret("aws-secrets-manager", externalSecretSpec);

    // Simulasi Rotasi Kredensial di Vault (Password diubah di AWS)
    console.log("=== BAGIAN 4: SIMULASI ROTASI KREDENSIAL TERPUSAT ===");
    await sleep(200);
    eso.setCloudSecret("prod/fintech/database", {
        DB_USER: "fintech_admin",
        DB_PASS: "SecretPass2026_ROTATED_v2"
    });

    // ESO mendeteksi dan memperbarui native secret otomatis
    eso.syncExternalSecret("aws-secrets-manager", externalSecretSpec);

    // Verifikasi Secret Terkini di K8s
    const activeSecret = eso.k8sSecretsStore.get("payment-db-native-secret");
    const decodedPass = Buffer.from(activeSecret.data.DB_PASS, 'base64').toString('utf8');
    console.log(`Hasil Verifikasi Native Secret di Kluster:`);
    console.log(`  -> DB_PASS (Base64) : ${activeSecret.data.DB_PASS}`);
    console.log(`  -> DB_PASS (Decoded): ${decodedPass}`);
    console.log(`  ✅ [ROTASI SUKSES] Password baru terpropagasi ke kluster secara otomatis!\n`);

    console.log("=== PERIKSA KEAMANAN FILE PERMISSION (defaultMode) ===");
    console.log("❌ BAD  : defaultMode: 0644 -> File secret bisa dibaca oleh user proses lain di kontainer.");
    console.log("✅ GOOD : defaultMode: 0400 -> File secret strictly Read-Only khusus untuk pemilik UID proses.");
}

run().catch(console.error);
