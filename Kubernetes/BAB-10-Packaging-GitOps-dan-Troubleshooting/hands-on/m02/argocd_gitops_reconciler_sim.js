/**
 * ArgoCD GitOps Reconciler & SRE Troubleshooting Simulator
 * 
 * Mensimulasikan dua sistem produksi vital:
 * 1. ArgoCD Continuous Reconciliation Engine:
 *    - Deteksi Drift antara Git State (Desired) vs Kubernetes Live State.
 *    - Penegakan Self-Healing otomatis saat terjadi perubahan manual tak terotorisasi.
 * 2. SRE Diagnostic Debugger Engine:
 *    - Diagnosa Exit Code 137 (OOMKilled by Linux Kernel).
 *    - Diagnosa CrashLoopBackOff via log --previous inspection.
 *    - Diagnosa Service Zero Endpoints akibat Selector Mismatch.
 */

const ANSI = {
  reset: "\x1b[0m",
  bold: "\x1b[1m",
  green: "\x1b[32m",
  cyan: "\x1b[36m",
  yellow: "\x1b[33m",
  red: "\x1b[31m",
  magenta: "\x1b[35m"
};

function log(module, msg, color = ANSI.reset) {
  console.log(`${color}[${module}] ${msg}${ANSI.reset}`);
}

// ================= 1. ARGOCD RECONCILER SIMULATOR =================
class ArgoCDReconciler {
  constructor(gitRepoUrl, targetNamespace) {
    this.repoUrl = gitRepoUrl;
    this.namespace = targetNamespace;
    this.syncPolicy = { automated: { selfHeal: true, prune: true } };
    this.gitState = {
      name: "payment-deployment",
      replicas: 3,
      image: "myregistry.io/payment:v2.4.1",
      commitSha: "a81c4e9"
    };
    this.liveClusterState = JSON.parse(JSON.stringify(this.gitState));
    this.status = { sync: "Synced", health: "Healthy" };
  }

  simulateManualIntervention(unauthorizedChanges) {
    log("rogue-user", `Engineer mengeksekusi manual 'kubectl edit deployment' di cluster live...`, ANSI.red);
    this.liveClusterState = { ...this.liveClusterState, ...unauthorizedChanges };
    log("live-cluster", `State Berubah Liar: Replicas=${this.liveClusterState.replicas}, Image=${this.liveClusterState.image}`, ANSI.red);
  }

  reconcile() {
    log("argocd-controller", `=== Menjalankan Rekonsiliasi Loop (Git: ${this.gitState.commitSha}) ===`, ANSI.bold);

    // Bandingkan Desired State (Git) vs Live State (Cluster)
    const isDrifted = (
      this.gitState.replicas !== this.liveClusterState.replicas ||
      this.gitState.image !== this.liveClusterState.image
    );

    if (isDrifted) {
      this.status.sync = "OutOfSync";
      log("argocd-controller", `DRIFT TERDETEKSI! Status: OutOfSync`, ANSI.yellow);
      log("argocd-controller", `Perbedaan (Diff):`, ANSI.yellow);
      log("argocd-diff", `- Live Cluster: Replicas=${this.liveClusterState.replicas}, Image=${this.liveClusterState.image}`, ANSI.red);
      log("argocd-diff", `+ Git Repo    : Replicas=${this.gitState.replicas}, Image=${this.gitState.image}`, ANSI.green);

      if (this.syncPolicy.automated.selfHeal) {
        log("argocd-selfheal", `Mekanisme 'selfHeal: true' aktif! Menimpa perubahan cluster live kembali ke state Git...`, ANSI.magenta);
        this.liveClusterState = JSON.parse(JSON.stringify(this.gitState));
        this.status.sync = "Synced";
        log("argocd-selfheal", `SELF-HEAL SUKSES! Live cluster kembali sinkron 100% dengan Git (Status: Synced/Healthy)`, ANSI.green);
      }
    } else {
      log("argocd-controller", `Cluster sinkron sempurna dengan Git (Status: Synced/Healthy). Tidak ada drift.`, ANSI.green);
    }
  }
}

// ================= 2. SRE DIAGNOSTIC DEBUGGER ENGINE =================
class SREDebugger {
  static diagnosePodFailure(podStatus) {
    log("sre-debugger", `Menganalisis Insiden Pod: '${podStatus.name}' di namespace '${podStatus.namespace}'...`, ANSI.bold);

    // Kasus 1: OOMKilled
    if (podStatus.lastState && podStatus.lastState.exitCode === 137) {
      log("diagnostic-tree", `Status: Terminated, Exit Code: 137 (128 + 9 SIGKILL)`, ANSI.red);
      log("diagnostic-tree", `AKAR MASALAH: Out-Of-Memory (OOMKilled) oleh Linux Kernel!`, ANSI.red);
      log("diagnostic-tree", `Penjelasan: Container mengonsumsi RAM melebihi resources.limits.memory (${podStatus.memoryLimit}).`, ANSI.yellow);
      log("diagnostic-tree", `REKOMENDASI RUNBOOK:`, ANSI.green);
      log("diagnostic-tree", `1. Periksa memory leak via heap profile atau profiler APM.`, ANSI.green);
      log("diagnostic-tree", `2. Naikkan resources.limits.memory dari ${podStatus.memoryLimit} menjadi 2x lipat di file manifest Git.`, ANSI.green);
      return;
    }

    // Kasus 2: CrashLoopBackOff dengan Exit Code 1
    if (podStatus.restartCount > 3 && podStatus.status === "CrashLoopBackOff") {
      log("diagnostic-tree", `Status: CrashLoopBackOff, Restart Count: ${podStatus.restartCount}`, ANSI.red);
      log("diagnostic-tree", `Memeriksa log sesaat sebelum crash: 'kubectl logs ${podStatus.name} --previous' ...`, ANSI.cyan);
      log("container-log", `[FATAL ERROR] Environment variable 'DATABASE_PASSWORD' is not set! Process panic.`, ANSI.red);
      log("diagnostic-tree", `AKAR MASALAH: Application Configuration / Missing Secret Error.`, ANSI.red);
      log("diagnostic-tree", `REKOMENDASI RUNBOOK: Pastikan Secret/ConfigMap terikat dengan benar pada spec.containers[].env.`, ANSI.green);
      return;
    }

    log("diagnostic-tree", `Tidak ada anomali terdeteksi pada Pod.`, ANSI.green);
  }

  static diagnoseServiceEndpoints(serviceSpec, podList) {
    log("sre-debugger", `Mendiagnosa HTTP 503 Bad Gateway pada Service '${serviceSpec.name}'...`, ANSI.bold);

    const matchingPods = podList.filter(pod => {
      return Object.entries(serviceSpec.selector).every(([k, v]) => pod.labels[k] === v);
    });

    log("service-check", `Service Selector: ${JSON.stringify(serviceSpec.selector)}`, ANSI.cyan);
    log("service-check", `Endpoints Ditemukan: ${matchingPods.length} Pod`, matchingPods.length > 0 ? ANSI.green : ANSI.red);

    if (matchingPods.length === 0) {
      log("diagnostic-tree", `AKAR MASALAH: Selector Mismatch! Zero Endpoints!`, ANSI.red);
      log("diagnostic-tree", `Label Pod yang ada saat ini:`, ANSI.yellow);
      for (const p of podList) {
        log("diagnostic-tree", `-> Pod '${p.name}': Labels = ${JSON.stringify(p.labels)}`, ANSI.yellow);
      }
      log("diagnostic-tree", `REKOMENDASI RUNBOOK: Samakan metadata.labels Pod dengan spec.selector Service!`, ANSI.green);
    } else {
      log("diagnostic-tree", `Routing Service normal. Traffic diteruskan ke Pod: [${matchingPods.map(p => p.name).join(", ")}]`, ANSI.green);
    }
  }
}

// ================= SIMULASI EKSEKUSI =================
console.log(`${ANSI.bold}================================================================${ANSI.reset}`);
console.log(`${ANSI.bold}      ARGOCD GITOPS RECONCILER & SRE TROUBLESHOOTING SIM        ${ANSI.reset}`);
console.log(`${ANSI.bold}================================================================${ANSI.reset}\n`);

// 1. Uji Coba GitOps & Self-Healing
console.log(`--- [SKENARIO 1: GITOPS DRIFT & AUTOMATED SELF-HEALING] ---`);
const argocd = new ArgoCDReconciler("https://github.com/corp/gitops.git", "payment-prod");

// Kondisi normal awal
argocd.reconcile();

// Terjadi intervensi liar manual
console.log("");
argocd.simulateManualIntervention({ replicas: 10, image: "unverified-dockerhub-image:latest" });

// ArgoCD Loop Rekonsiliasi berjalan
console.log("");
argocd.reconcile();

// 2. Uji Coba SRE Troubleshooting Runbook
console.log(`\n--- [SKENARIO 2: SRE RUNBOOK — DIAGNOSA OOMKILLED (EXIT 137)] ---`);
const oomPod = {
  name: "analytics-worker-0",
  namespace: "bigdata",
  memoryLimit: "512Mi",
  lastState: { exitCode: 137, reason: "OOMKilled" }
};
SREDebugger.diagnosePodFailure(oomPod);

console.log(`\n--- [SKENARIO 3: SRE RUNBOOK — DIAGNOSA CRASHLOOPBACKOFF & LOGS] ---`);
const crashPod = {
  name: "auth-service-79bf-x1",
  namespace: "security",
  restartCount: 5,
  status: "CrashLoopBackOff"
};
SREDebugger.diagnosePodFailure(crashPod);

console.log(`\n--- [SKENARIO 4: SRE RUNBOOK — DIAGNOSA ZERO ENDPOINTS HTTP 503] ---`);
const myService = {
  name: "frontend-svc",
  selector: { app: "frontend", tier: "web" }
};
const currentPods = [
  { name: "frontend-pod-1", labels: { app: "frontend", environment: "production" } }, // Kurang label tier=web!
  { name: "frontend-pod-2", labels: { app: "frontend", environment: "production" } }
];
SREDebugger.diagnoseServiceEndpoints(myService, currentPods);

console.log(`\n${ANSI.bold}Seluruh skenario GitOps Reconciler dan SRE Troubleshooting tervalidasi!${ANSI.reset}`);
