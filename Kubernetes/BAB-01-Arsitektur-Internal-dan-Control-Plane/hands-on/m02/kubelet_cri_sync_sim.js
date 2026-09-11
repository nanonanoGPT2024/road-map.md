/**
 * hands-on/m02/kubelet_cri_sync_sim.js
 * 
 * Simulasi Arsitektur Worker Node:
 * 1. Kubelet Sync Loop & Pod Lifecycle Reconciliation.
 * 2. CRI (Container Runtime Interface) gRPC Handshake (RunPodSandbox -> CreateContainer -> StartContainer).
 * 3. Cgroup Driver Validation (Systemd vs Cgroupfs mismatch audit).
 * 4. NodeLease Heartbeat Mechanism (coordination.k8s.io).
 * 5. Kube-Proxy Service Routing Engine (iptables vs IPVS lookup).
 */

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

console.log("================================================================================");
console.log("        KUBERNETES WORKER NODE (KUBELET, CRI, KUBE-PROXY) SIMULATOR             ");
console.log("================================================================================\n");

class WorkerNodeSimulator {
    constructor(nodeName, kubeletCgroup, containerdCgroup) {
        this.nodeName = nodeName;
        this.kubeletCgroup = kubeletCgroup;
        this.containerdCgroup = containerdCgroup;
        this.activeSandboxes = new Map();
        this.iptablesRules = [];
        this.leaseRenewCount = 0;
    }

    log(agent, message) {
        const ts = new Date().toISOString().substring(11, 19);
        console.log(`[${ts}] [${agent.padEnd(14)}] ${message}`);
    }

    // Step 1: Validate Cgroup Driver Harmony
    verifyCgroupDrivers() {
        this.log("NODE_INIT", `Memverifikasi cgroup driver: Kubelet=[${this.kubeletCgroup}], containerd=[${this.containerdCgroup}]`);
        if (this.kubeletCgroup !== this.containerdCgroup) {
            this.log("NODE_INIT", `[FATAL ERROR] Cgroup driver mismatch! Kubelet uses '${this.kubeletCgroup}', but containerd uses '${this.containerdCgroup}'.`);
            this.log("NODE_INIT", `  Kernel panics / cgroups conflict: Kubelet fails to boot!\n`);
            return false;
        }
        this.log("NODE_INIT", `  -> Cgroup driver terpadu (Unified systemd driver). Host OS stabil!\n`);
        return true;
    }

    // Step 2: CRI gRPC Lifecycle Simulation
    async syncPod(podSpec) {
        this.log("KUBELET_SYNC", `Menerima instruksi Pod: "${podSpec.metadata.name}" (Namespace: ${podSpec.metadata.namespace})`);

        // 2.1 RunPodSandbox (CNI + Network Namespace + Pause Container)
        this.log("CRI_GRPC", `gRPC Call -> RuntimeService.RunPodSandbox(Config)`);
        await sleep(150);
        const podIp = `10.244.1.${Math.floor(Math.random() * 200) + 10}`;
        const sandboxId = `sbx_${Math.random().toString(36).substring(2, 8)}`;
        this.log("CNI_PLUGIN", `  [CNI] Mengalokasikan veth interface & Pod IP: ${podIp}`);
        this.log("CRI_GRPC", `  -> Sandbox aktif (ID: ${sandboxId}) dengan Pause Container PID 12401`);

        // 2.2 Create Container
        const containerSpec = podSpec.spec.containers[0];
        this.log("CRI_GRPC", `gRPC Call -> RuntimeService.CreateContainer("${containerSpec.name}", Image: "${containerSpec.image}")`);
        await sleep(120);
        const containerId = `ctr_${Math.random().toString(36).substring(2, 8)}`;
        this.log("CRI_GRPC", `  -> Container dikonfigurasi: cgroups CPU limit=${containerSpec.resources.limits.cpu}, Memory=${containerSpec.resources.limits.memory}`);

        // 2.3 Start Container
        this.log("CRI_GRPC", `gRPC Call -> RuntimeService.StartContainer("${containerId}")`);
        await sleep(100);
        this.log("CRI_GRPC", `  -> Proses aplikasi berjalan normal via runc.`);

        this.activeSandboxes.set(sandboxId, {
            podName: podSpec.metadata.name,
            ip: podIp,
            containerId: containerId,
            status: "Running"
        });

        this.log("KUBELET_PLEG", `PLEG mendeteksi Pod "${podSpec.metadata.name}" berstatus RUNNING. Melaporkan status ke apiserver.\n`);
        return { sandboxId, podIp };
    }

    // Step 3: NodeLease Heartbeat Simulator
    sendHeartbeatLease() {
        this.leaseRenewCount++;
        this.log("NODE_LEASE", `Memperbarui coordination.k8s.io/v1 Lease untuk node: "${this.nodeName}" (Sequence #${this.leaseRenewCount}). Status: READY.`);
    }

    // Step 4: Kube-Proxy Translation Simulator
    programKubeProxyService(serviceName, clusterIp, targetPort, podIps, mode = "iptables") {
        this.log("KUBE_PROXY", `Mendeteksi Service: "${serviceName}" (ClusterIP: ${clusterIp}:${targetPort})`);
        
        if (mode === "iptables") {
            this.log("KUBE_PROXY", `  [Mode: iptables] Memprogram rantai netfilter Linux host:`);
            this.log("KUBE_PROXY", `    Chain KUBE-SERVICES -> -d ${clusterIp}/32 -p tcp --dport ${targetPort} -j KUBE-SVC-XYZ`);
            podIps.forEach((ip, idx) => {
                const prob = (1 / (podIps.length - idx)).toFixed(2);
                this.log("KUBE_PROXY", `    Chain KUBE-SVC-XYZ  -> -m statistic --mode random --probability ${prob} -j DNAT to ${ip}:${targetPort}`);
            });
        } else {
            this.log("KUBE_PROXY", `  [Mode: IPVS] Memprogram virtual server Linux IPVS Hash Table:`);
            this.log("KUBE_PROXY", `    Virtual Server: ${clusterIp}:${targetPort} (Scheduler: Round-Robin)`);
            podIps.forEach(ip => {
                this.log("KUBE_PROXY", `      -> Real Server Destination: ${ip}:${targetPort} (Weight: 1)`);
            });
        }
        console.log("");
    }
}

async function run() {
    console.log("=== PENGUJIAN 1: AUDIT KESELARASAN DRIVER CGROUP ===");
    // Test mismatched node
    const brokenNode = new WorkerNodeSimulator("worker-node-broken", "systemd", "cgroupfs");
    brokenNode.verifyCgroupDrivers();

    // Valid production node
    const prodNode = new WorkerNodeSimulator("worker-node-01", "systemd", "systemd");
    const isHealthy = prodNode.verifyCgroupDrivers();
    if (!isHealthy) return;

    console.log("=== PENGUJIAN 2: SIKLUS HIDUP POD PADA CRI & KUBELET ===");
    const pod = {
        metadata: { name: "checkout-api-pod-1", namespace: "production" },
        spec: {
            containers: [{
                name: "checkout-api",
                image: "payflow/api:v1.2.0",
                resources: {
                    limits: { cpu: "500m", memory: "256Mi" }
                }
            }]
        }
    };

    const { podIp } = await prodNode.syncPod(pod);

    console.log("=== PENGUJIAN 3: HEARTBEAT NODE LEASE SUPERVISI ===");
    prodNode.sendHeartbeatLease();
    prodNode.sendHeartbeatLease();
    console.log("");

    console.log("=== PENGUJIAN 4: TRANSLASI SERVICE OLEH KUBE-PROXY (IPTABLES VS IPVS) ===");
    const endpoints = [podIp, "10.244.1.46", "10.244.2.88"];
    prodNode.programKubeProxyService("payment-svc", "10.96.14.20", 8080, endpoints, "iptables");
    prodNode.programKubeProxyService("payment-svc", "10.96.14.20", 8080, endpoints, "ipvs");

    console.log("=== KESIMPULAN ARSITEKTUR WORKER NODE ===");
    console.log("1. Kubelet memprogram OCI container via protokol CRI gRPC.");
    console.log("2. Wajib menggunakan 'cgroupDriver: systemd' di Kubelet dan Containerd.");
    console.log("3. IPVS lebih efisien dari iptables untuk penanganan Service berskala besar.");
}

run().catch(console.error);
