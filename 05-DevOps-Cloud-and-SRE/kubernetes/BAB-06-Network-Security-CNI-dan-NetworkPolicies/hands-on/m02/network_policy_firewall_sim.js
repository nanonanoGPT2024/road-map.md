/**
 * hands-on/m02/network_policy_firewall_sim.js
 * 
 * Simulasi NetworkPolicy Firewall & Mikrosegmentasi Zero-Trust:
 * 1. Default Open vs Zero-Trust Network Baseline.
 * 2. 3-Tier Microsegmentation Rules (Frontend -> Backend -> Database).
 * 3. CoreDNS Port 53 Egress Exemption Rule.
 * 4. Lateral Movement & Data Exfiltration Attack Simulation (Blocked!).
 */

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

console.log("================================================================================");
console.log("       KUBERNETES NETWORKPOLICY ZERO-TRUST FIREWALL SIMULATOR v2.0              ");
console.log("================================================================================\n");

class NetworkPolicyFirewallSimulator {
    constructor() {
        this.pods = new Map();
        this.policies = [];
        this.defaultDenyIngress = false;
        this.defaultDenyEgress = false;
    }

    log(stage, msg) {
        const ts = new Date().toISOString().substring(11, 19);
        console.log(`[${ts}] [${stage.padEnd(16)}] ${msg}`);
    }

    registerPod(id, name, namespace, labels, ip) {
        this.pods.set(id, { id, name, namespace, labels, ip });
    }

    addPolicy(policy) {
        this.policies.push(policy);
        this.log("POLICY_APPLY", `NetworkPolicy "${policy.name}" diterapkan di namespace: "${policy.namespace}"`);
    }

    // Evaluate Packet against NetworkPolicies
    evaluatePacket(srcPodId, dstPodId, protocol, dstPort) {
        const src = this.pods.get(srcPodId);
        const dst = this.pods.get(dstPodId);

        console.log(`[TRAFFIC EVALUATION] ${src.name} (${src.ip}) ---> ${dst.name} (${dst.ip}:${dstPort}/${protocol})`);

        // Check Egress on Source Pod
        let egressAllowed = !this.defaultDenyEgress;
        if (this.defaultDenyEgress) {
            for (const p of this.policies) {
                if (p.namespace === src.namespace && this.matchesSelector(src.labels, p.podSelector)) {
                    if (p.egress) {
                        for (const rule of p.egress) {
                            if (this.matchesRule(rule.to, rule.ports, dst, protocol, dstPort)) {
                                egressAllowed = true;
                                break;
                            }
                        }
                    }
                }
            }
        }

        if (!egressAllowed) {
            console.log(`  ❌ [EGRESS BLOCKED] Paket keluar dari ${src.name} di-drop oleh Egress NetworkPolicy!\n`);
            return false;
        }

        // Check Ingress on Destination Pod
        let ingressAllowed = !this.defaultDenyIngress;
        if (this.defaultDenyIngress) {
            for (const p of this.policies) {
                if (p.namespace === dst.namespace && this.matchesSelector(dst.labels, p.podSelector)) {
                    if (p.ingress) {
                        for (const rule of p.ingress) {
                            if (this.matchesRule(rule.from, rule.ports, src, protocol, dstPort)) {
                                ingressAllowed = true;
                                break;
                            }
                        }
                    }
                }
            }
        }

        if (!ingressAllowed) {
            console.log(`  ❌ [INGRESS BLOCKED] Paket masuk ke ${dst.name}:${dstPort} di-drop oleh Ingress NetworkPolicy!\n`);
            return false;
        }

        console.log(`  ✅ [PACKET ALLOWED] Koneksi berhasil! Packet diteruskan oleh kernel filter.\n`);
        return true;
    }

    matchesSelector(labels, selector) {
        if (!selector || Object.keys(selector).length === 0) return true; // match all
        for (const [k, v] of Object.entries(selector)) {
            if (labels[k] !== v) return false;
        }
        return true;
    }

    matchesRule(selectors, ports, peerPod, protocol, port) {
        // Check port
        let portMatches = false;
        if (!ports || ports.length === 0) portMatches = true;
        else {
            portMatches = ports.some(p => p.protocol.toUpperCase() === protocol.toUpperCase() && p.port === port);
        }
        if (!portMatches) return false;

        // Check peer selector
        if (!selectors || selectors.length === 0) return true;
        for (const s of selectors) {
            if (s.podSelector && this.matchesSelector(peerPod.labels, s.podSelector.matchLabels)) {
                return true;
            }
        }
        return false;
    }
}

async function run() {
    const fw = new NetworkPolicyFirewallSimulator();

    // Register Pods in cluster
    fw.registerPod("fe", "frontend-pod", "production", { app: "frontend", tier: "web" }, "10.244.1.10");
    fw.registerPod("be", "backend-pod", "production", { app: "backend", tier: "api" }, "10.244.1.20");
    fw.registerPod("db", "database-pod", "production", { app: "database", tier: "data" }, "10.244.1.30");
    fw.registerPod("rogue", "compromised-pod", "production", { app: "miner", tier: "unknown" }, "10.244.1.99");
    fw.registerPod("dns", "coredns-pod", "kube-system", { "k8s-app": "kube-dns" }, "10.96.0.10");

    console.log("=== SKENARIO 1: DEFAULT K8S JARINGAN TERBUKA (PERMISSIVE) ===");
    console.log("Tanpa NetworkPolicy, pod mana pun bebas mengakses database langsung:");
    fw.evaluatePacket("rogue", "db", "TCP", 5432);

    console.log("=== SKENARIO 2: MENGAKTIFKAN ZERO-TRUST DEFAULT-DENY BASELINE ===");
    fw.defaultDenyIngress = true;
    fw.defaultDenyEgress = true;
    console.log("Semua pintu ditutup. Uji coba koneksi frontend -> backend:");
    fw.evaluatePacket("fe", "be", "TCP", 8080); // Should be blocked

    console.log("=== SKENARIO 3: MENERAPKAN ATURAN MIKROSEGMENTASI 3-TIER ===");
    
    // Policy 1: Backend Security Policy (Allow Ingress from FE:8080, Egress to DB:5432 + DNS:53)
    fw.addPolicy({
        name: "backend-policy",
        namespace: "production",
        podSelector: { app: "backend" },
        ingress: [
            { from: [{ podSelector: { matchLabels: { app: "frontend" } } }], ports: [{ protocol: "TCP", port: 8080 }] }
        ],
        egress: [
            { to: [{ podSelector: { matchLabels: { app: "database" } } }], ports: [{ protocol: "TCP", port: 5432 }] },
            { to: [{ podSelector: { matchLabels: { "k8s-app": "kube-dns" } } }], ports: [{ protocol: "UDP", port: 53 }] }
        ]
    });

    // Policy 2: Database Security Policy (Allow Ingress ONLY from BE:5432)
    fw.addPolicy({
        name: "database-policy",
        namespace: "production",
        podSelector: { app: "database" },
        ingress: [
            { from: [{ podSelector: { matchLabels: { app: "backend" } } }], ports: [{ protocol: "TCP", port: 5432 }] }
        ],
        egress: [] // Deny all egress from DB!
    });

    // Policy 3: Frontend Security Policy (Allow Egress to BE:8080)
    fw.addPolicy({
        name: "frontend-policy",
        namespace: "production",
        podSelector: { app: "frontend" },
        ingress: [{ from: [], ports: [{ protocol: "TCP", port: 80 }] }],
        egress: [
            { to: [{ podSelector: { matchLabels: { app: "backend" } } }], ports: [{ protocol: "TCP", port: 8080 }] }
        ]
    });
    console.log("");

    console.log("=== SKENARIO 4: VERIFIKASI AKSES LEGAL VS PERETAS ===");
    // Valid path 1: Frontend -> Backend (8080)
    fw.evaluatePacket("fe", "be", "TCP", 8080);

    // Valid path 2: Backend -> Database (5432)
    fw.evaluatePacket("be", "db", "TCP", 5432);

    // Valid path 3: Backend -> CoreDNS (53)
    fw.evaluatePacket("be", "dns", "UDP", 53);

    // Attack 1: Rogue Pod trying to hack Database direct
    console.log("[SIMULASI PERETASAN 1: Rogue Pod scanning Database direct]");
    fw.evaluatePacket("rogue", "db", "TCP", 5432);

    // Attack 2: Frontend trying to bypass Backend to access Database direct
    console.log("[SIMULASI PERETASAN 2: Frontend trying to touch Database direct]");
    fw.evaluatePacket("fe", "db", "TCP", 5432);

    console.log("=== KESIMPULAN ARSITEKTUR KEAMANAN JARINGAN ===");
    console.log("1. Default-Deny All Ingress & Egress wajib diaktifkan di production.");
    console.log("2. Selalu izinkan CoreDNS UDP 53 di setiap egress policy.");
    console.log("3. Mikrosegmentasi 3-tier berhasil melumpuhkan lateral movement peretas.");
}

run().catch(console.error);
