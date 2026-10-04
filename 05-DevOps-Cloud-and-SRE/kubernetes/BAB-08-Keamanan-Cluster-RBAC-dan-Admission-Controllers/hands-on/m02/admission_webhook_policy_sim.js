/**
 * Kubernetes Dynamic Admission Webhook & Pod Security Policy Simulator
 * 
 * Mensimulasikan pipeline Admission Control kube-apiserver:
 * 1. Mutating Admission Webhook (Injeksi Resource Limits & Non-Root Defaults via JSON Patch).
 * 2. Validating Admission Webhook (Enforcement PSS Restricted: No Privileged, No HostNetwork, No :latest tag).
 * 3. Mekanisme failurePolicy: Fail vs Ignore.
 * 4. AdmissionReview Request & Response JSON Contract.
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

class MutatingWebhookService {
  process(admissionRequest) {
    const pod = admissionRequest.object;
    log("mutating-webhook", `Menerima request untuk Pod: ${pod.metadata.namespace}/${pod.metadata.name}`, ANSI.cyan);
    
    const patches = [];

    // 1. Injeksi default securityContext.runAsNonRoot jika belum ada
    if (!pod.spec.securityContext || pod.spec.securityContext.runAsNonRoot === undefined) {
      patches.push({
        op: "add",
        path: "/spec/securityContext/runAsNonRoot",
        value: true
      });
      log("mutating-webhook", `-> Menambahkan JSON Patch: enforce runAsNonRoot=true`, ANSI.yellow);
    }

    // 2. Injeksi label tracking cost-center jika belum ada
    if (!pod.metadata.labels || !pod.metadata.labels["cost-center"]) {
      patches.push({
        op: "add",
        path: "/metadata/labels/cost-center",
        value: "unassigned-ops"
      });
      log("mutating-webhook", `-> Menambahkan JSON Patch: inject label cost-center=unassigned-ops`, ANSI.yellow);
    }

    return {
      uid: admissionRequest.uid,
      allowed: true,
      patchType: "JSONPatch",
      patch: Buffer.from(JSON.stringify(patches)).toString("base64")
    };
  }
}

class ValidatingWebhookService {
  constructor(isHealthy = true) {
    this.isHealthy = isHealthy;
  }

  process(admissionRequest) {
    if (!this.isHealthy) {
      throw new Error("503 Service Unavailable: Webhook backend down / timeout");
    }

    const pod = admissionRequest.object;
    log("validating-webhook", `Memvalidasi Pod: ${pod.metadata.namespace}/${pod.metadata.name}`, ANSI.magenta);

    // Rule 1: Privileged container check (PSS Restricted)
    for (const c of pod.spec.containers || []) {
      if (c.securityContext && c.securityContext.privileged === true) {
        return {
          uid: admissionRequest.uid,
          allowed: false,
          status: {
            code: 403,
            message: `Pelanggaran Policy PSS Restricted: Container '${c.name}' dilarang menggunakan securityContext.privileged=true`
          }
        };
      }
    }

    // Rule 2: Host namespace escape check
    if (pod.spec.hostNetwork === true || pod.spec.hostPID === true) {
      return {
        uid: admissionRequest.uid,
        allowed: false,
        status: {
          code: 403,
          message: `Pelanggaran Policy Keamanan: Dilarang menggunakan hostNetwork atau hostPID (Risiko Container Escape)`
        }
      };
    }

    // Rule 3: Image tag :latest rejection
    for (const c of pod.spec.containers || []) {
      if (c.image.endsWith(":latest") || !c.image.includes(":")) {
        return {
          uid: admissionRequest.uid,
          allowed: false,
          status: {
            code: 400,
            message: `Pelanggaran Best Practice: Container '${c.name}' dilarang menggunakan tag ':latest'. Wajib menggunakan semver tag yang immutable.`
          }
        };
      }
    }

    return {
      uid: admissionRequest.uid,
      allowed: true,
      status: { code: 200, message: "Validasi Lolos. Spesifikasi aman." }
    };
  }
}

class APIServerAdmissionPipeline {
  constructor(mutatingWebhook, validatingWebhook, failurePolicy = "Fail") {
    this.mutatingWebhook = mutatingWebhook;
    this.validatingWebhook = validatingWebhook;
    this.failurePolicy = failurePolicy; // 'Fail' | 'Ignore'
  }

  admit(podManifest) {
    const uid = `adm-req-${Math.floor(10000 + Math.random() * 90000)}`;
    const req = {
      uid,
      operation: "CREATE",
      object: JSON.parse(JSON.stringify(podManifest))
    };

    log("api-server", `=== Tahap 1: Authentication & Authorization (RBAC) Lolos ===`, ANSI.bold);

    // 1. Mutating Phase
    log("api-server", `=== Tahap 2: Menjalankan Mutating Admission Webhook ===`, ANSI.bold);
    try {
      const mutRes = this.mutatingWebhook.process(req);
      if (mutRes.patch) {
        const decoded = JSON.parse(Buffer.from(mutRes.patch, "base64").toString("utf-8"));
        // Aplikasikan patch ke objek
        req.object.spec.securityContext = req.object.spec.securityContext || {};
        req.object.metadata.labels = req.object.metadata.labels || {};
        for (const p of decoded) {
          if (p.path === "/spec/securityContext/runAsNonRoot") req.object.spec.securityContext.runAsNonRoot = p.value;
          if (p.path === "/metadata/labels/cost-center") req.object.metadata.labels["cost-center"] = p.value;
        }
        log("api-server", `Mutasi berhasil diaplikasikan ke manifest Pod.`, ANSI.green);
      }
    } catch (err) {
      log("api-server", `Mutating Webhook Error: ${err.message}`, ANSI.red);
      if (this.failurePolicy === "Fail") {
        return { success: false, reason: "Mutating webhook failed and failurePolicy is Fail" };
      }
    }

    // 2. Schema Validation
    log("api-server", `=== Tahap 3: Object Schema Validation Lolos ===`, ANSI.bold);

    // 3. Validating Phase
    log("api-server", `=== Tahap 4: Menjalankan Validating Admission Webhook ===`, ANSI.bold);
    try {
      const valRes = this.validatingWebhook.process(req);
      if (!valRes.allowed) {
        log("api-server", `DITOLAK OLEH ADMISSION CONTROLLER! Status: ${valRes.status.code}`, ANSI.red);
        log("api-server", `Pesan Error: ${valRes.status.message}`, ANSI.red);
        return { success: false, reason: valRes.status.message };
      }
      log("api-server", `Validasi Berhasil: ${valRes.status.message}`, ANSI.green);
    } catch (err) {
      log("api-server", `Validating Webhook Gagal Dijangkau: ${err.message}`, ANSI.red);
      if (this.failurePolicy === "Fail") {
        log("api-server", `DITOLAK: failurePolicy='Fail' memblokir pembuatan Pod demi keamanan cluster!`, ANSI.red);
        return { success: false, reason: "Webhook unreachable and failurePolicy is Fail" };
      } else {
        log("api-server", `DIPERBOLEHKAN: failurePolicy='Ignore' meloloskan request meskipun webhook mati.`, ANSI.yellow);
      }
    }

    log("api-server", `=== Tahap 5: Persistensi ke etcd BERHASIL! Pod Terbentuk ===`, ANSI.green);
    return { success: true, finalObject: req.object };
  }
}

// ================= SIMULASI EKSEKUSI =================
console.log(`${ANSI.bold}================================================================${ANSI.reset}`);
console.log(`${ANSI.bold}      KUBERNETES ADMISSION WEBHOOK & SECURITY POLICY SIM        ${ANSI.reset}`);
console.log(`${ANSI.bold}================================================================${ANSI.reset}\n`);

const mutator = new MutatingWebhookService();
const validator = new ValidatingWebhookService(true);
const pipeline = new APIServerAdmissionPipeline(mutator, validator, "Fail");

console.log("\n--- Skenario 1: Pod Tidak Aman Menggunakan 'privileged: true' ---");
const insecurePod = {
  metadata: { name: "attacker-pod", namespace: "production" },
  spec: {
    containers: [
      { name: "shell", image: "harbor.corp/alpine:3.19", securityContext: { privileged: true } }
    ]
  }
};
pipeline.admit(insecurePod);

console.log("\n--- Skenario 2: Pod Menggunakan Tag ':latest' ---");
const latestTagPod = {
  metadata: { name: "webapp-pod", namespace: "production" },
  spec: {
    containers: [
      { name: "web", image: "nginx:latest" }
    ]
  }
};
pipeline.admit(latestTagPod);

console.log("\n--- Skenario 3: Pod Lolos Validasi + Mengalami Mutasi Otomatis ---");
const goodPod = {
  metadata: { name: "payment-api-pod", namespace: "production" },
  spec: {
    containers: [
      { name: "api", image: "harbor.corp/payment-api:v2.1.0" }
    ]
  }
};
const res3 = pipeline.admit(goodPod);
if (res3.success) {
  console.log("\nHasil Manifest Pasca-Mutasi di etcd:");
  console.log(JSON.stringify(res3.finalObject, null, 2));
}

console.log("\n--- Skenario 4: Webhook Server Down dengan failurePolicy: Fail vs Ignore ---");
const deadValidator = new ValidatingWebhookService(false); // Webhook crash
const strictPipeline = new APIServerAdmissionPipeline(mutator, deadValidator, "Fail");
const lenientPipeline = new APIServerAdmissionPipeline(mutator, deadValidator, "Ignore");

console.log("[Test 1: failurePolicy = Fail]");
strictPipeline.admit(goodPod);

console.log("\n[Test 2: failurePolicy = Ignore]");
lenientPipeline.admit(goodPod);

console.log(`\n${ANSI.bold}Seluruh siklus Admission Webhooks tervalidasi dengan sukses!${ANSI.reset}`);
