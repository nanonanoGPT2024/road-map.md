/**
 * hands-on/m01/service_proxy_iptables_sim.js
 * 
 * Simulasi Service Networking, CoreDNS, ndots:5, & EndpointSlices:
 * 1. CoreDNS FQDN Resolution (service.namespace.svc.cluster.local).
 * 2. ndots: 5 Latency Problem & Optimization Demonstration.
 * 3. EndpointSlices Chunking Engine (Breaking 250 pods into slices of 100).
 * 4. kube-proxy L4 Load Balancing & Dynamic Endpoint Eviction.
 */

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

console.log("================================================================================");
console.log("       KUBERNETES SERVICE DISCOVERY, COREDNS, & KUBE-PROXY SIMULATOR            ");
console.log("================================================================================\n");

class CoreDnsSimulator {
    constructor() {
        this.records = new Map();
        this.searchDomains = [
            "default.svc.cluster.local",
            "svc.cluster.local",
            "cluster.local"
        ];
    }

    registerService(name, namespace, clusterIp) {
        const fqdn = `${name}.${namespace}.svc.cluster.local`;
        this.records.set(fqdn, clusterIp);
        this.records.set(`${name}.${namespace}`, clusterIp);
        this.records.set(name, clusterIp); // short name
    }

    // Step 1: Demonstrate ndots: 5 latency trap
    resolveDnsQuery(queryDomain, ndotsSetting = 5) {
        console.log(`[DNS QUERY] Resolving: "${queryDomain}" (ndots: ${ndotsSetting})`);
        const dotCount = (queryDomain.match(/\./g) || []).length;
        let queryAttempts = 0;

        if (dotCount < ndotsSetting) {
            console.log(`  -> Dot count (${dotCount}) < ndots (${ndotsSetting}). Mencoba search domains internal terlebih dahulu:`);
            for (const search of this.searchDomains) {
                queryAttempts++;
                const attemptedFqdn = `${queryDomain}.${search}`;
                if (this.records.has(attemptedFqdn)) {
                    console.log(`    [Attempt ${queryAttempts}] MATCH FOUND: ${attemptedFqdn} -> ${this.records.get(attemptedFqdn)}`);
                    return { ip: this.records.get(attemptedFqdn), attempts: queryAttempts };
                } else {
                    console.log(`    [Attempt ${queryAttempts}: NXDOMAIN] ${attemptedFqdn} (Gagal! +2ms latency)`);
                }
            }
        }

        // Final query as absolute domain
        queryAttempts++;
        console.log(`  -> [Attempt ${queryAttempts}: SUCCESS] Mencoba query absolute domain "${queryDomain}" -> External Public IP (203.0.113.45)`);
        console.log(`  ⚠️  LATENCY PENALTY: Query eksternal memakan ${queryAttempts}x round-trips akibat ndots: ${ndotsSetting}!\n`);
        return { ip: "203.0.113.45", attempts: queryAttempts };
    }
}

class EndpointSliceSimulator {
    // Step 2: Slice chunking
    static chunkPodsIntoSlices(serviceName, totalPods, maxPerSlice = 100) {
        console.log(`=== TAHAP 2: ENDPOINTSLICES CHUNKING ENGINE ===`);
        console.log(`Membagi ${totalPods} pods untuk Service "${serviceName}" ke dalam EndpointSlices (Max ${maxPerSlice} per slice):`);
        
        const slices = [];
        let sliceIndex = 0;

        for (let i = 0; i < totalPods; i += maxPerSlice) {
            const countInThisSlice = Math.min(maxPerSlice, totalPods - i);
            const sliceName = `${serviceName}-slice-${sliceIndex}`;
            slices.push({ name: sliceName, endpointsCount: countInThisSlice });
            console.log(`  -> [Created] ${sliceName.padEnd(28)}: Menampung ${countInThisSlice} Pod IPs.`);
            sliceIndex++;
        }

        console.log(`Keuntungan: Jika 1 Pod mati, Kubelet HANYA memperbarui 1 slice kecil tanpa mem-broadcast 250 pod ke seluruh node kluster!\n`);
        return slices;
    }
}

class KubeProxySimulator {
    constructor() {
        this.services = new Map();
    }

    registerServiceEndpoints(clusterIp, port, endpoints) {
        this.services.set(`${clusterIp}:${port}`, endpoints);
    }

    // Step 3: Simulate Packet Load Balancing
    routePacket(clientIp, targetClusterIp, targetPort) {
        const key = `${targetClusterIp}:${targetPort}`;
        const healthyBackends = this.services.get(key) || [];

        if (healthyBackends.length === 0) {
            console.log(`[NETFILTER PACKET DROP] SYN packet from ${clientIp} to ${key} dropped: No endpoints available! (HTTP 503)`);
            return;
        }

        // Round-robin selection
        const pickedPod = healthyBackends[Math.floor(Math.random() * healthyBackends.length)];
        console.log(`[KUBE-PROXY IPVS ROUTE] Client: ${clientIp} -> VIP: ${key}`);
        console.log(`  -> DNAT Kernel Translation: Target diubah ke Pod aktual: ${pickedPod}`);
        console.log(`  -> Packet successfully delivered!\n`);
    }

    evictEndpoint(clusterIp, port, unhealthyPodIp) {
        const key = `${clusterIp}:${port}`;
        let endpoints = this.services.get(key) || [];
        endpoints = endpoints.filter(ip => ip !== unhealthyPodIp);
        this.services.set(key, endpoints);
        console.log(`[ENDPOINT EVICTION] Readiness probe failed on ${unhealthyPodIp}!`);
        console.log(`  -> IP ${unhealthyPodIp} segera dicabut dari kernel routing table. Sisa active pods: [${endpoints.join(', ')}]\n`);
    }
}

async function run() {
    // 1. CoreDNS & ndots:5 Test
    console.log("=== TAHAP 1: COREDNS RESOLUSI FQDN & NDOTS: 5 LATENCY TEST ===");
    const dns = new CoreDnsSimulator();
    dns.registerService("payment-api", "production", "10.96.45.100");

    // Resolving internal service
    console.log("[Internal Query Test]");
    dns.resolveDnsQuery("payment-api.production.svc.cluster.local", 5);

    // Resolving external domain with default ndots: 5 (Problematic!)
    console.log("[External Query Test: Default ndots: 5 Trap]");
    dns.resolveDnsQuery("api.stripe.com", 5);

    // Resolving with optimized ndots: 2 (Optimized!)
    console.log("[External Query Test: Optimized ndots: 2 Setting]");
    dns.resolveDnsQuery("api.stripe.com", 2);

    // 2. EndpointSlices Chunking
    EndpointSliceSimulator.chunkPodsIntoSlices("checkout-svc", 250, 100);

    // 3. Kube-Proxy L4 Load Balancing Test
    console.log("=== TAHAP 3: KUBE-PROXY LOAD BALANCING & LIVE EVICTION ===");
    const proxy = new KubeProxySimulator();
    const serviceVip = "10.96.45.100";
    const servicePort = 8080;
    
    proxy.registerServiceEndpoints(serviceVip, servicePort, [
        "10.244.1.25:8080",
        "10.244.2.33:8080",
        "10.244.3.41:8080"
    ]);

    // Send requests
    proxy.routePacket("10.244.0.5", serviceVip, servicePort);
    proxy.routePacket("10.244.0.8", serviceVip, servicePort);

    // Simulate node crash / readiness probe fail
    proxy.evictEndpoint(serviceVip, servicePort, "10.244.2.33:8080");

    // Route packet after eviction
    proxy.routePacket("10.244.0.9", serviceVip, servicePort);

    console.log("=== REKOMENDASI BEST PRACTICE ===");
    console.log("1. Selalu gunakan Service ClusterIP untuk abstraksi Pod fana.");
    console.log("2. Gunakan ndots: 2 di PodSpec jika sering memanggil API eksternal.");
    console.log("3. EndpointSlices otomatis menangani penskalaan ribuan Pod per service.");
}

run().catch(console.error);
