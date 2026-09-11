/**
 * hands-on/m01/k8s_control_plane_sim.js
 * 
 * Simulasi Siklus Hidup Request Kubernetes Control Plane:
 * 1. kube-apiserver Pipeline (AuthN -> AuthZ -> Mutating -> Schema -> Validating -> etcd).
 * 2. etcd Raft Quorum Check (Simulasi 3-node cluster).
 * 3. kube-controller-manager (Deployment -> ReplicaSet -> Pods Creation).
 * 4. kube-scheduler (Two-phase: Filtering / Predicates & Scoring / Priorities).
 */

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

console.log("================================================================================");
console.log("       KUBERNETES CONTROL PLANE ARCHITECTURE & REQUEST PIPELINE SIMULATOR       ");
console.log("================================================================================\n");

class EtcdClusterSimulator {
    constructor(nodeCount = 3) {
        this.nodeCount = nodeCount;
        this.quorumRequired = Math.floor(nodeCount / 2) + 1;
        this.nodes = Array.from({ length: nodeCount }, (_, i) => ({ id: `etcd-node-${i + 1}`, alive: true }));
        this.database = new Map();
    }

    async commitTransaction(key, value) {
        const aliveNodes = this.nodes.filter(n => n.alive).length;
        if (aliveNodes < this.quorumRequired) {
            throw new Error(`etcd Raft Consensus Failed! Active nodes: ${aliveNodes}, Quorum required: ${this.quorumRequired}`);
        }
        await sleep(100);
        this.database.set(key, value);
        return { committed: true, acks: aliveNodes, key };
    }
}

class ControlPlaneSimulator {
    constructor() {
        this.etcd = new EtcdClusterSimulator(3);
        this.workerNodes = [
            { name: "worker-node-1", totalMemMb: 8192, usedMemMb: 6000, totalCpu: 4, usedCpu: 3.2 },
            { name: "worker-node-2", totalMemMb: 8192, usedMemMb: 2000, totalCpu: 4, usedCpu: 1.0 },
            { name: "worker-node-3", totalMemMb: 4096, usedMemMb: 3800, totalCpu: 2, usedCpu: 1.9 }
        ];
        this.podsQueue = [];
    }

    log(component, message) {
        const ts = new Date().toISOString().substring(11, 19);
        console.log(`[${ts}] [${component.padEnd(16)}] ${message}`);
    }

    // Step 1: kube-apiserver Pipeline
    async processApiRequest(token, manifest) {
        this.log("KUBE_APISERVER", `Menerima request HTTP POST /apis/apps/v1/namespaces/default/deployments`);

        // 1.1 Authentication
        this.log("KUBE_APISERVER", `[1/6 AuthN] Memvalidasi token pengguna: ${token.substring(0, 12)}...`);
        if (token !== "bearer_devops_admin_valid_token") {
            throw new Error("401 Unauthorized: Invalid Token");
        }
        this.log("KUBE_APISERVER", `  -> Identitas terverifikasi: User="cluster-admin", Groups=["system:masters"]`);

        // 1.2 Authorization (RBAC)
        this.log("KUBE_APISERVER", `[2/6 AuthZ] Mengevaluasi aturan RBAC (ClusterRoleBinding)...`);
        this.log("KUBE_APISERVER", `  -> RBAC ALLOW: User diizinkan membuat 'deployments' di namespace 'default'.`);

        // 1.3 Mutating Admission Webhook
        this.log("KUBE_APISERVER", `[3/6 Mutating] Menjalankan Mutating Webhook (Sidecar & Annotation Injector)...`);
        manifest.metadata.annotations = { "injected-by": "production-mutating-webhook", "created-at": new Date().toISOString() };
        this.log("KUBE_APISERVER", `  -> Metadata diperkaya dengan default annotations.`);

        // 1.4 Schema Validation
        this.log("KUBE_APISERVER", `[4/6 SchemaVal] Memeriksa integritas skema OpenAPI v3 JSON schema...`);
        if (!manifest.spec || !manifest.spec.replicas || !manifest.spec.template) {
            throw new Error("422 Unprocessable Entity: Invalid Deployment Schema");
        }
        this.log("KUBE_APISERVER", `  -> Skema valid!`);

        // 1.5 Validating Admission Webhook (Security Policies)
        this.log("KUBE_APISERVER", `[5/6 Validating] Mengevaluasi Kyverno / OPA Gatekeeper Admission Policies...`);
        if (manifest.spec.template.spec.containers[0].image.endsWith(":latest")) {
            console.log(`  [SECURITY WARNING] Image tag ':latest' terdeteksi, kebijakan admission melempar warning audit.`);
        }
        this.log("KUBE_APISERVER", `  -> Validating webhook LULUS.`);

        // 1.6 etcd Commit
        this.log("KUBE_APISERVER", `[6/6 etcd Commit] Menyimpan state ke etcd cluster via gRPC...`);
        const key = `/registry/deployments/default/${manifest.metadata.name}`;
        const commitResult = await this.etcd.commitTransaction(key, manifest);
        this.log("ETCD_RAFT", `Transisi state berhasil di-commit! Quorum ACKs: ${commitResult.acks}/3. Key: ${key}\n`);

        return manifest;
    }

    // Step 2: kube-controller-manager (Reconciliation Loop)
    async reconcileDeployment(deployment) {
        this.log("CONTROLLER_MGR", `[DeploymentController] Terpicu oleh event ADDED Deployment: "${deployment.metadata.name}"`);
        const replicas = deployment.spec.replicas;
        this.log("CONTROLLER_MGR", `  -> Desired Replicas = ${replicas}. Membuat ReplicaSet: "${deployment.metadata.name}-rs-84b2"`);
        
        await sleep(150);
        this.log("CONTROLLER_MGR", `[ReplicaSetController] Mendeteksi kekurangan Pod. Actual = 0, Desired = ${replicas}`);
        
        for (let i = 1; i <= replicas; i++) {
            const pod = {
                name: `${deployment.metadata.name}-${Math.random().toString(36).substring(2, 7)}`,
                reqMemMb: 1024,
                reqCpu: 0.5,
                nodeName: null, // Unassigned!
                status: "Pending"
            };
            this.podsQueue.push(pod);
            this.log("CONTROLLER_MGR", `  -> Membuat Pod: ${pod.name} (spec.nodeName = null, Status = Pending)`);
        }
        console.log("");
    }

    // Step 3: kube-scheduler (Filtering & Scoring)
    async schedulePendingPods() {
        this.log("KUBE_SCHEDULER", `Memeriksa antrean Pods yang belum dijadwalkan (spec.nodeName == null)...`);
        
        for (const pod of this.podsQueue) {
            this.log("KUBE_SCHEDULER", `\n--- Menjadwalkan Pod: "${pod.name}" (Req: ${pod.reqMemMb}MB RAM, ${pod.reqCpu} CPU) ---`);
            
            // Phase 1: Filtering (Predicates)
            const feasibleNodes = [];
            for (const node of this.workerNodes) {
                const availMem = node.totalMemMb - node.usedMemMb;
                const availCpu = node.totalCpu - node.usedCpu;

                if (availMem >= pod.reqMemMb && availCpu >= pod.reqCpu) {
                    this.log("KUBE_SCHEDULER", `  [Filter Predicate: PASS] ${node.name} -> Sisa RAM: ${availMem}MB, Sisa CPU: ${availCpu.toFixed(1)}`);
                    feasibleNodes.push(node);
                } else {
                    this.log("KUBE_SCHEDULER", `  [Filter Predicate: FAIL] ${node.name} -> Tidak cukup resource (Sisa RAM: ${availMem}MB)`);
                }
            }

            if (feasibleNodes.length === 0) {
                this.log("KUBE_SCHEDULER", `  [ERROR] 0/${this.workerNodes.length} nodes available. Pod "${pod.name}" tetap PENDING!`);
                continue;
            }

            // Phase 2: Scoring (Priorities - LeastAllocated strategy)
            this.log("KUBE_SCHEDULER", `  [Phase 2: Scoring] Menghitung prioritas LeastAllocated untuk penyeimbangan beban:`);
            let bestNode = null;
            let highestScore = -1;

            for (const node of feasibleNodes) {
                const freeMemRatio = (node.totalMemMb - node.usedMemMb) / node.totalMemMb;
                const score = Math.round(freeMemRatio * 100);
                this.log("KUBE_SCHEDULER", `    -> ${node.name} Score: ${score}/100`);

                if (score > highestScore) {
                    highestScore = score;
                    bestNode = node;
                }
            }

            // Binding Phase
            pod.nodeName = bestNode.name;
            pod.status = "Scheduled";
            bestNode.usedMemMb += pod.reqMemMb;
            bestNode.usedCpu += pod.reqCpu;
            this.log("KUBE_SCHEDULER", `  [BINDING] Pod "${pod.name}" berhasil di-bind ke node: "${bestNode.name}"!`);
        }
        console.log("");
    }
}

async function run() {
    const cp = new ControlPlaneSimulator();

    const deploymentManifest = {
        apiVersion: "apps/v1",
        kind: "Deployment",
        metadata: { name: "payment-gateway", namespace: "default" },
        spec: {
            replicas: 3,
            template: {
                spec: {
                    containers: [{ name: "api", image: "payflow/api:v1.0.0" }]
                }
            }
        }
    };

    console.log("=== SIMULASI SIKLUS HIDUP REQUEST DEKLARATIF KUBERNETES ===");
    const deployment = await cp.processApiRequest("bearer_devops_admin_valid_token", deploymentManifest);

    console.log("=== SIMULASI REKONSILIASI KONTROLER (KUBE-CONTROLLER-MANAGER) ===");
    await cp.reconcileDeployment(deployment);

    console.log("=== SIMULASI PENJADWALAN POD (KUBE-SCHEDULER FILTERING & SCORING) ===");
    await cp.schedulePendingPods();

    console.log("=== HASIL AKHIR PENEMPATAN WORKLOAD DI WORKER NODE ===");
    console.log("--------------------------------------------------------------------------------");
    console.log(String("Pod Name").padEnd(30) + String("Assigned Node").padEnd(25) + "Final Status");
    console.log("--------------------------------------------------------------------------------");
    for (const p of cp.podsQueue) {
        console.log(p.name.padEnd(30) + (p.nodeName || "Unassigned").padEnd(25) + p.status.toUpperCase());
    }
    console.log("--------------------------------------------------------------------------------\n");
}

run().catch(console.error);
