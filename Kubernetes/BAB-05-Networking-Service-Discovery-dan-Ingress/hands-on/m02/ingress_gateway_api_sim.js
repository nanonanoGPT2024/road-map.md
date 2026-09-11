/**
 * hands-on/m02/ingress_gateway_api_sim.js
 * 
 * Simulasi Ingress Layer 7 Routing, cert-manager ACME, & Gateway API Traffic Splitting:
 * 1. Ingress L7 Host & Path Routing Engine with TLS Termination.
 * 2. cert-manager ACME HTTP-01 Challenge & Automatic Secret Issuance.
 * 3. Kubernetes Gateway API Engine (HTTPRoute).
 * 4. Canary Weighted Traffic Splitting (80% v1 vs 20% v2) & Header-based Routing.
 */

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

console.log("================================================================================");
console.log("       KUBERNETES INGRESS, CERT-MANAGER, & GATEWAY API SIMULATOR v2.6           ");
console.log("================================================================================\n");

class IngressControllerSimulator {
    constructor() {
        this.routes = [];
        this.tlsCertificates = new Map();
    }

    log(agent, msg) {
        const ts = new Date().toISOString().substring(11, 19);
        console.log(`[${ts}] [${agent.padEnd(16)}] ${msg}`);
    }

    registerTlsCert(secretName, domain, certPem) {
        this.tlsCertificates.set(secretName, { domain, certPem });
        this.log("TLS_MANAGER", `Sertifikat SSL terdaftar untuk "${domain}" (Secret: ${secretName})`);
    }

    addRoute(host, pathPrefix, targetService, port) {
        this.routes.push({ host, pathPrefix, targetService, port });
        this.log("INGRESS_ROUTER", `Mendaftarkan rute L7: https://${host}${pathPrefix} -> ${targetService}:${port}`);
    }

    // Step 1: Simulate Ingress Routing & TLS termination
    handleIncomingRequest(protocol, host, path) {
        this.log("EDGE_GATEWAY", `Menerima request: ${protocol}://${host}${path}`);
        
        if (protocol === "https") {
            const hasCert = Array.from(this.tlsCertificates.values()).some(c => c.domain === host);
            if (!hasCert) {
                this.log("TLS_TERMINATION", `  ❌ [SSL ERROR] Tidak ada sertifikat valid untuk domain "${host}"!`);
                return { status: 526, body: "Invalid SSL Certificate" };
            }
            this.log("TLS_TERMINATION", `  🔒 [TLS 1.3 Handshake OK] Decrypted traffic using certificate.`);
        }

        const match = this.routes.find(r => r.host === host && path.startsWith(r.pathPrefix));
        if (match) {
            this.log("INGRESS_ROUTER", `  ✅ [PATH MATCH] Rute cocok! Mem-forward traffic ke upstream -> ${match.targetService}:${match.port}\n`);
            return { status: 200, upstream: match.targetService };
        } else {
            this.log("INGRESS_ROUTER", `  ❌ [404 NOT FOUND] Tidak ada rute yang cocok untuk ${path}\n`);
            return { status: 404, body: "Not Found" };
        }
    }
}

// Step 2: cert-manager ACME HTTP-01 Simulator
class CertManagerSimulator {
    static async issueLetsEncryptCert(domain, issuerName = "letsencrypt-prod") {
        console.log("=== TAHAP 2: SIMULASI CERT-MANAGER ACME HTTP-01 CHALLENGE ===");
        console.log(`[1/4] Mendeteksi Ingress baru dengan annotasi cert-manager.io/cluster-issuer: "${issuerName}"`);
        console.log(`[2/4] Membuat objek Certificate & Order untuk domain: "${domain}"`);
        await sleep(150);

        const token = "acme_token_" + Math.random().toString(36).substring(2, 10);
        const challengeUrl = `http://${domain}/.well-known/acme-challenge/${token}`;
        console.log(`[3/4] Menerbitkan ACME HTTP-01 Challenge Endpoint: ${challengeUrl}`);
        await sleep(150);
        console.log(`      Let's Encrypt bot melakukan HTTP GET ke ${challengeUrl}... HTTP 200 OK!`);

        console.log(`[4/4] Kepemilikan domain terverifikasi! Let's Encrypt menandatangani sertifikat x509.`);
        const secretName = `${domain.replace(/\./g, '-')}-tls`;
        console.log(`      Menyimpan sertifikat SSL publik & private key ke Kubernetes Secret: "${secretName}"`);
        console.log(`      ✅ Sertifikat SSL aktif dan otomatis di-renew 30 hari sebelum kedaluwarsa!\n`);
        return secretName;
    }
}

// Step 3: Kubernetes Gateway API & Canary Traffic Splitter
class GatewayApiSimulator {
    constructor() {
        this.canaryWeights = { v1: 80, v2: 20 };
        this.v1Requests = 0;
        this.v2Requests = 0;
    }

    routeHttpRequest(headers, path) {
        // Priority 1: Header-based routing (Canary bypass)
        if (headers['x-canary'] === 'true') {
            this.v2Requests++;
            return "payment-service-v2 (Header Match: X-Canary)";
        }

        // Priority 2: Weighted Random Routing (80/20)
        const randomPercent = Math.random() * 100;
        if (randomPercent < this.canaryWeights.v1) {
            this.v1Requests++;
            return "payment-service-v1 (Weight: 80%)";
        } else {
            this.v2Requests++;
            return "payment-service-v2 (Weight: 20%)";
        }
    }

    printStats(total) {
        console.log(`Hasil Pembagian Traffic Gateway API (${total} Request):`);
        console.log(`  -> Version 1 (Stable) : ${this.v1Requests} requests (${((this.v1Requests / total) * 100).toFixed(1)}%)`);
        console.log(`  -> Version 2 (Canary) : ${this.v2Requests} requests (${((this.v2Requests / total) * 100).toFixed(1)}%)`);
        console.log(`✅ Canary traffic split berjalan presisi sesuai bobot konfigurasi!\n`);
    }
}

async function run() {
    console.log("=== TAHAP 1: INGRESS L7 HOST & PATH-BASED ROUTING ===");
    const ingress = new IngressControllerSimulator();

    // Setup SSL via cert-manager
    const secretName = await CertManagerSimulator.issueLetsEncryptCert("api.payflow.com");
    ingress.registerTlsCert(secretName, "api.payflow.com", "-----BEGIN CERTIFICATE-----...");

    // Register Routes
    ingress.addRoute("api.payflow.com", "/payment", "payment-svc", 8080);
    ingress.addRoute("api.payflow.com", "/auth", "auth-svc", 3000);
    console.log("");

    // Simulate incoming client requests
    ingress.handleIncomingRequest("https", "api.payflow.com", "/payment/v1/checkout");
    ingress.handleIncomingRequest("https", "api.payflow.com", "/auth/login");
    ingress.handleIncomingRequest("https", "api.payflow.com", "/unknown-path");

    // Gateway API Canary Testing
    console.log("=== TAHAP 3: KUBERNETES GATEWAY API CANARY TRAFFIC SPLIT (HTTPRoute) ===");
    const gateway = new GatewayApiSimulator();
    const totalRequests = 100;

    console.log(`Mengirim ${totalRequests} request ke Gateway API HTTPRoute (80% v1, 20% v2)...`);
    for (let i = 1; i <= totalRequests; i++) {
        gateway.routeHttpRequest({}, "/v1/checkout");
    }
    gateway.printStats(totalRequests);

    // Test Header-based routing
    console.log("[Testing Header-based Routing: x-canary: true]");
    const target = gateway.routeHttpRequest({ 'x-canary': 'true' }, "/v1/checkout");
    console.log(`  -> Target: ${target} (Direct bypass to new version!)\n`);

    console.log("=== KESIMPULAN REKOMENDASI EDGE ROUTING ===");
    console.log("1. Gunakan 1 Ingress Controller untuk menghemat biaya Cloud Load Balancer.");
    console.log("2. Gunakan cert-manager untuk eliminasi risiko sertifikat SSL kedaluwarsa.");
    console.log("3. Gunakan Gateway API untuk canary deployment dan kontrol rilis multi-tim.");
}

run().catch(console.error);
