/**
 * Helm v3 & Kustomize Packaging Simulator Engine
 * 
 * Mensimulasikan dua paradigma manajemen konfigurasi Kubernetes:
 * 1. Helm v3: Evaluasi template, parsing values.yaml, pelacakan rilis Secret, dan rollback.
 * 2. Kustomize: Layering Base + Overlays, Strategic Merge Patch, JSON 6902 Patch, dan ConfigMap SHA Hash generator.
 */

const crypto = require("crypto");

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

// ================= 1. HELM SIMULATOR =================
class HelmSimulator {
  constructor() {
    this.releaseHistory = new Map(); // releaseName -> [ { revision, values, rendered, status } ]
  }

  render(chartName, values, releaseName) {
    log("helm-engine", `Rendering Chart '${chartName}' dengan Release Name: '${releaseName}'`, ANSI.cyan);

    const fullname = `${releaseName}-${chartName}`;
    const replicas = values.replicaCount || 1;
    const img = `${values.image.repository}:${values.image.tag}`;
    const port = values.service.port || 80;

    let manifest = `---
# Source: ${chartName}/templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${fullname}
  labels:
    app.kubernetes.io/managed-by: Helm
    app.kubernetes.io/instance: ${releaseName}
spec:
  replicas: ${replicas}
  selector:
    matchLabels:
      app: ${fullname}
  template:
    metadata:
      labels:
        app: ${fullname}
    spec:
      containers:
        - name: ${chartName}
          image: "${img}"
          ports:
            - containerPort: ${port}`;

    if (values.ingress && values.ingress.enabled) {
      manifest += `\n---
# Source: ${chartName}/templates/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ${fullname}-ingress
spec:
  rules:
    - host: ${values.ingress.host}
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: ${fullname}
                port:
                  number: ${port}`;
    }

    return manifest;
  }

  install(releaseName, chartName, values, namespace = "default") {
    const rendered = this.render(chartName, values, releaseName);
    const revision = 1;
    const history = [{ revision, values, rendered, status: "deployed" }];
    this.releaseHistory.set(releaseName, history);

    // Simpan release metadata sebagai Secret
    const secretName = `sh.helm.release.v1.${releaseName}.v1`;
    log("helm-storage", `Menyimpan state rilis ke Secret: ${namespace}/${secretName}`, ANSI.green);
    log("helm-cli", `STATUS: deployed, REVISION: ${revision}`, ANSI.green);
    return rendered;
  }

  upgrade(releaseName, chartName, newValues) {
    const history = this.releaseHistory.get(releaseName);
    if (!history) throw new Error(`Release ${releaseName} tidak ditemukan!`);

    const newRevision = history.length + 1;
    log("helm-cli", `Melakukan upgrade release '${releaseName}' ke REVISION: ${newRevision}`, ANSI.yellow);

    const rendered = this.render(chartName, newValues, releaseName);
    history.push({ revision: newRevision, values: newValues, rendered, status: "deployed" });

    log("helm-storage", `Menyimpan state rilis Secret baru: sh.helm.release.v1.${releaseName}.v${newRevision}`, ANSI.green);
    return rendered;
  }

  rollback(releaseName, targetRevision) {
    const history = this.releaseHistory.get(releaseName);
    const target = history.find(h => h.revision === targetRevision);
    if (!target) throw new Error(`Revisi ${targetRevision} tidak ditemukan!`);

    const nextRev = history.length + 1;
    log("helm-cli", `ROLLBACK: Mengembalikan release '${releaseName}' ke state revisi ${targetRevision} (Dibuat sebagai Revisi ${nextRev})`, ANSI.magenta);
    history.push({ revision: nextRev, values: target.values, rendered: target.rendered, status: "deployed" });
    return target.rendered;
  }
}

// ================= 2. KUSTOMIZE SIMULATOR =================
class KustomizeSimulator {
  render(baseManifest, overlayConfig) {
    log("kustomize-engine", `Mengeksekusi Kustomize Overlay untuk namespace: '${overlayConfig.namespace}'`, ANSI.cyan);

    // 1. Generate ConfigMap dengan SHA Hash
    const configContent = overlayConfig.configData || "default-config";
    const shaHash = crypto.createHash("sha256").update(configContent).digest("hex").substring(0, 8);
    const configMapName = `${overlayConfig.namePrefix || ""}${overlayConfig.configMapBaseName}-${shaHash}`;

    log("kustomize-generator", `ConfigMapGenerator: Dibuat '${configMapName}' (Hash SHA256 konten diinjeksikan)`, ANSI.yellow);

    // 2. Clone dan modifikasi manifest base (Strategic Merge & JSON Patching)
    const deployment = JSON.parse(JSON.stringify(baseManifest.deployment));
    const service = JSON.parse(JSON.stringify(baseManifest.service));

    // Injeksi NamePrefix & Namespace
    deployment.metadata.name = `${overlayConfig.namePrefix || ""}${deployment.metadata.name}`;
    deployment.metadata.namespace = overlayConfig.namespace;
    service.metadata.name = `${overlayConfig.namePrefix || ""}${service.metadata.name}`;
    service.metadata.namespace = overlayConfig.namespace;

    // Strategic Merge Patch: Replicas & Envs
    if (overlayConfig.patches && overlayConfig.patches.replicas) {
      deployment.spec.replicas = overlayConfig.patches.replicas;
      log("kustomize-patch", `StrategicMerge: Menimpa replicas menjadi ${overlayConfig.patches.replicas}`, ANSI.green);
    }

    // Injeksi ConfigMap Ref ke container
    deployment.spec.template.spec.containers[0].envFrom = [
      { configMapRef: { name: configMapName } }
    ];

    return {
      configMap: {
        apiVersion: "v1",
        kind: "ConfigMap",
        metadata: { name: configMapName, namespace: overlayConfig.namespace },
        data: { "app.json": configContent }
      },
      deployment,
      service
    };
  }
}

// ================= SIMULASI EKSEKUSI =================
console.log(`${ANSI.bold}================================================================${ANSI.reset}`);
console.log(`${ANSI.bold}       HELM v3 & KUSTOMIZE PACKAGING SIMULATION ENGINE          ${ANSI.reset}`);
console.log(`${ANSI.bold}================================================================${ANSI.reset}\n`);

// 1. Demonstrasi Helm v3
console.log(`--- [BAGIAN 1: HELM v3 LIFECYCLE & ROLLBACK] ---`);
const helm = new HelmSimulator();

const valuesV1 = {
  replicaCount: 2,
  image: { repository: "myregistry.io/payment-api", tag: "v1.0.0" },
  service: { port: 8080 },
  ingress: { enabled: true, host: "api.company.com" }
};

log("user-action", "User menjalankan: helm install payment ./my-chart -f values-v1.yaml", ANSI.bold);
helm.install("payment", "payment-chart", valuesV1, "production");

// Upgrade ke V2 (Tag v2.0.0, replicas: 5)
console.log("");
log("user-action", "User menjalankan: helm upgrade payment ./my-chart --set image.tag=v2.0.0 --set replicaCount=5", ANSI.bold);
const valuesV2 = { ...valuesV1, replicaCount: 5, image: { repository: "myregistry.io/payment-api", tag: "v2.0.0" } };
helm.upgrade("payment", "payment-chart", valuesV2);

// Terjadi bug di V2 -> Rollback ke V1
console.log("");
log("user-action", "Bug terdeteksi di V2! User menjalankan: helm rollback payment 1", ANSI.bold);
helm.rollback("payment", 1);

// 2. Demonstrasi Kustomize
console.log(`\n--- [BAGIAN 2: KUSTOMIZE BASE & OVERLAY PATCHING] ---`);
const kustomize = new KustomizeSimulator();

const baseApp = {
  deployment: {
    apiVersion: "apps/v1",
    kind: "Deployment",
    metadata: { name: "checkout-service" },
    spec: {
      replicas: 1,
      template: {
        spec: {
          containers: [{ name: "web", image: "checkout:base", ports: [{ containerPort: 80 }] }]
        }
      }
    }
  },
  service: {
    apiVersion: "v1",
    kind: "Service",
    metadata: { name: "checkout-service" },
    spec: { ports: [{ port: 80, targetPort: 80 }] }
  }
};

const prodOverlay = {
  namespace: "production",
  namePrefix: "prod-",
  configMapBaseName: "checkout-config",
  configData: JSON.stringify({ database_host: "prod-db.internal", max_connections: 500 }),
  patches: { replicas: 12 }
};

log("user-action", "User menjalankan: kubectl kustomize overlays/prod/", ANSI.bold);
const kustomizedOutput = kustomize.render(baseApp, prodOverlay);

console.log("\nHasil Akhir Render Kustomize (Production Environment):");
console.log(JSON.stringify(kustomizedOutput, null, 2));

console.log(`\n${ANSI.bold}Seluruh alur kerja Helm v3 dan Kustomize berhasil disimulasikan!${ANSI.reset}`);
