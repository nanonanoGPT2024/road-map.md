/**
 * hands-on/m01/cni_ebpf_routing_sim.js
 * 
 * Simulasi CNI Network Datapath:
 * 1. CNI veth Pair & IPAM Allocation Lifecycle.
 * 2. Overlay VXLAN (iptables O(N) + MTU Overhead) vs Cilium eBPF (Socket Bypass O(1)).
 * 3. MTU Fragmentation & Packet Drop Inspection (MTU 1500 vs 1450).
 * 4. Hubble L7 Observability Flow Event Logging.
 */

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

console.log("================================================================================");
console.log("     KUBERNETES CNI (OVERLAY VXLAN VS CILIUM eBPF) DATAPATH SIMULATOR           ");
console.log("================================================================================\n");

class CniDatapathSimulator {
    constructor() {
        this.allocatedIps = new Set();
        this.nextHostId = 10;
    }

    log(subsystem, msg) {
        const ts = new Date().toISOString().substring(11, 19);
        console.log(`[${ts}] [${subsystem.padEnd(16)}] ${msg}`);
    }

    // Step 1: CNI Setup veth pair & IPAM
    allocatePodInterface(podName, namespace) {
        this.log("CNI_IPAM", `Menerima instruksi CNI ADD untuk Pod: "${podName}" (${namespace})`);
        const podIp = `10.244.1.${this.nextHostId++}`;
        const vethHost = `veth${Math.random().toString(36).substring(2, 6)}`;
        const vethPod = "eth0";

        this.log("CNI_DRIVER", `  -> Membuat veth pair: [${vethHost} di Host Node] <=====> [${vethPod} di Pod NetNS]`);
        this.log("CNI_IPAM", `  -> Menetapkan IP Address: ${podIp}/24 (Gateway: 10.244.1.1)`);
        this.log("CNI_DRIVER", `  -> Interface status: UP. MTU: 1500. Rute lokal aktif.\n`);
        return { podIp, vethHost };
    }

    // Step 2: Simulate Legacy VXLAN + iptables Routing
    simulateVxlanIptablesDatapath(packetPayloadBytes, iptablesRulesCount = 15000) {
        console.log("=== PENGUJIAN 1: OVERLAY VXLAN + IPTABLES (LEGACY CNI) ===");
        this.log("VXLAN_ENGINE", `Memproses paket payload ${packetPayloadBytes} byte melalui tumpukan iptables...`);

        // Check MTU Penalty (Outer IP 20B + UDP 8B + VXLAN 8B + Ethernet 14B = 50 Byte Overhead)
        const maxPayload = 1500 - 50; // 1450 Bytes
        if (packetPayloadBytes > maxPayload) {
            this.log("VXLAN_ENGINE", `  ❌ [MTU MISMATCH ERROR] Ukuran paket (${packetPayloadBytes}B) melebihi batas MTU VXLAN (${maxPayload}B)!`);
            this.log("VXLAN_ENGINE", `  Paket terfragmentasi / di-drop oleh switch (DF-bit set). Koneksi hang!\n`);
            return;
        }

        // Simulate iptables O(N) traversal
        const start = Date.now();
        this.log("NETFILTER", `Mengevaluasi ${iptablesRulesCount} baris rule iptables secara sekuensial O(N)...`);
        // Simulated latency for traversal
        const elapsedMicros = (iptablesRulesCount * 0.05).toFixed(0);
        this.log("NETFILTER", `  -> Selesai melintasi rantai KUBE-SERVICES & FORWARD (${elapsedMicros} μs CPU overhead)`);
        this.log("VXLAN_ENGINE", `  -> Enkapsulasi paket ke dalam UDP Port 4789. Paket dikirim ke wire.\n`);
    }

    // Step 3: Simulate Cilium eBPF Socket-Level Datapath
    simulateCiliumEbpfDatapath(packetPayloadBytes) {
        console.log("=== PENGUJIAN 2: CILIUM eBPF DIRECT ROUTING (NEXT-GEN) ===");
        this.log("EBPF_ENGINE", `Memproses paket payload ${packetPayloadBytes} byte via eBPF program hook di TC/Socket layer...`);
        
        // No encapsulation overhead in direct routing mode
        this.log("EBPF_ENGINE", `  -> Direct flat routing aktif (Zero encapsulation overhead). MTU standar 1500 penuh!`);
        
        // eBPF Map O(1) Lookup
        this.log("EBPF_MAPS", `Lookup BPF_MAP_SERVICE & BPF_MAP_ENDPOINTS via hash table (Kompleksitas O(1) konstan)...`);
        this.log("EBPF_ENGINE", `  -> Bypass seluruh tumpukan netfilter & iptables!`);
        this.log("EBPF_ENGINE", `  -> Paket diteruskan langsung ke veth interface tujuan dalam 1.2 μs!`);
        this.log("EBPF_ENGINE", `  ✅ Throughput 100% wire-speed tercapai dengan 0% CPU lock.\n`);
    }

    // Step 4: Hubble Layer 7 Flow Visibility Output
    printHubbleFlowLogs() {
        console.log("=== PENGUJIAN 3: CILIUM HUBBLE LAYER 7 FLOW OBSERVABILITY ===");
        console.log(String("TIMESTAMP").padEnd(12) + String("SRC POD").padEnd(20) + String("DST POD").padEnd(20) + String("L7 PROTO").padEnd(10) + "STATUS / DETAILS");
        console.log("--------------------------------------------------------------------------------");
        console.log("07:04:12.100".padEnd(12) + "frontend-74b8".padEnd(20) + "payment-svc".padEnd(20) + "HTTP/1.1".padEnd(10) + "GET /v1/checkout -> 200 OK (0.8ms)");
        console.log("07:04:12.105".padEnd(12) + "payment-svc".padEnd(20) + "postgres-db".padEnd(20) + "TCP".padEnd(10) + "SYN -> Port 5432 (Established)");
        console.log("07:04:12.110".padEnd(12) + "auth-svc".padEnd(20) + "kube-dns".padEnd(20) + "DNS".padEnd(10) + "A? redis.default.svc -> 10.96.0.45");
        console.log("--------------------------------------------------------------------------------");
        console.log("✅ Visibilitas L7 penuh diperoleh langsung dari kernel tanpa memasang sidecar Envoy!\n");
    }
}

async function run() {
    const cni = new CniDatapathSimulator();

    // 1. Setup Pod Interface
    cni.allocatePodInterface("payment-api-pod-1", "production");

    // 2. VXLAN Test with 1480B (Triggers MTU error because 1480 + 50 = 1530 > 1500)
    cni.simulateVxlanIptablesDatapath(1480, 20000);

    // 3. VXLAN Test with safe 1400B
    cni.simulateVxlanIptablesDatapath(1400, 20000);

    // 4. Cilium eBPF Test with full 1480B (Passes cleanly!)
    cni.simulateCiliumEbpfDatapath(1480);

    // 5. Hubble L7 Observability
    cni.printHubbleFlowLogs();

    console.log("=== REKOMENDASI ARSITEKTUR CNI ===");
    console.log("1. Selalu kurangi MTU menjadi 1450 jika terpaksa menggunakan VXLAN.");
    console.log("2. Gunakan Cilium eBPF untuk kluster skala besar demi performa O(1).");
    console.log("3. Manfaatkan Hubble untuk debugging traffic Layer 7 tanpa sidecar.");
}

run().catch(console.error);
