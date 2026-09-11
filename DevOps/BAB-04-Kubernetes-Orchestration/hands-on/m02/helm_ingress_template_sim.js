/**
 * Hands-on M02: Helm Template Engine, Ingress L7 Router, & Rollback Simulator
 * Mengilustrasikan konsep:
 * 1. Helm Template Rendering (values.yaml -> Manifest YAML)
 * 2. Ingress Controller Virtual Host & Path Routing (Layer 7)
 * 3. Helm Release History & Instant Rollback
 *
 * Jalankan: node helm_ingress_template_sim.js
 */

const colors = {
  reset: '\x1b[0m',
  cyan: '\x1b[36m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  magenta: '\x1b[35m',
  red: '\x1b[31m',
  bold: '\x1b[1m'
};

// ==========================================
// 1. HELM TEMPLATE ENGINE SIMULATOR
// ==========================================
class HelmEngineSimulator {
  constructor(chartName) {
    this.chartName = chartName;
    this.releaseHistory = []; // list of revisions
  }

  renderManifest(values, releaseName, revision = 1) {
    console.log(`${colors.cyan}[HELM TEMPLATE] Rendering chart "${this.chartName}" (Release: ${releaseName}, Rev: ${revision})...${colors.reset}`);
    
    // Encode secret password ke base64 (standar K8s Secret)
    const encodedDbPass = Buffer.from(values.dbPassword || 'defaultPass').toString('base64');

    const rendered = {
      apiVersion: 'apps/v1',
      kind: 'Deployment',
      metadata: { name: `${releaseName}-deployment`, labels: { app: releaseName } },
      spec: {
        replicas: values.replicaCount,
        image: `${values.image.repository}:${values.image.tag}`,
        env: {
          DATABASE_HOST: values.dbHost || 'postgres-svc',
          DATABASE_PASSWORD_B64: encodedDbPass
        },
        resources: values.resources
      }
    };

    return rendered;
  }

  upgradeRelease(releaseName, newValues) {
    const newRev = this.releaseHistory.length + 1;
    const manifest = this.renderManifest(newValues, releaseName, newRev);

    this.releaseHistory.push({
      revision: newRev,
      updatedAt: new Date().toISOString(),
      status: 'DEPLOYED',
      values: newValues,
      manifest
    });

    console.log(`${colors.green}[HELM UPGRADE SUCCESS] Release "${releaseName}" berhasil di-deploy ke Revisi #${newRev}${colors.reset}\n`);
    return manifest;
  }

  rollback(releaseName, targetRevision) {
    console.log(`\n${colors.yellow}[HELM ROLLBACK] Memutar balik release "${releaseName}" ke Revisi #${targetRevision}...${colors.reset}`);
    const target = this.releaseHistory.find(r => r.revision === targetRevision);
    if (!target) {
      throw new Error(`Revisi #${targetRevision} tidak ditemukan dalam riwayat rilis!`);
    }

    const rollbackRev = this.releaseHistory.length + 1;
    this.releaseHistory.push({
      revision: rollbackRev,
      updatedAt: new Date().toISOString(),
      status: `ROLLED_BACK_TO_${targetRevision}`,
      values: target.values,
      manifest: target.manifest
    });

    console.log(`${colors.green}[ROLLBACK COMPLETED] Berhasil kembali ke konfigurasi Revisi #${targetRevision} (Revisi Aktif Sekarang: #${rollbackRev})${colors.reset}\n`);
    return target.manifest;
  }

  printHistory() {
    console.log(`\n${colors.bold}=== HELM RELEASE HISTORY (${this.chartName}) ===${colors.reset}`);
    console.log('REVISION\tUPDATED\t\t\tSTATUS\t\tIMAGE TAG\tREPLICAS');
    console.log('---------------------------------------------------------------------------------');
    this.releaseHistory.forEach(r => {
      console.log(`${r.revision}\t\t${r.updatedAt.substring(11, 19)}\t\t${r.status.padEnd(14)}\t${r.values.image.tag}\t\t${r.values.replicaCount}`);
    });
    console.log('---------------------------------------------------------------------------------\n');
  }
}

// ==========================================
// 2. KUBERNETES INGRESS L7 ROUTER SIMULATOR
// ==========================================
class IngressControllerSimulator {
  constructor() {
    this.rules = new Map(); // host + path -> target service
  }

  addRule(host, path, targetService) {
    const key = `${host}:${path}`;
    this.rules.set(key, targetService);
    console.log(`  ${colors.magenta}[INGRESS RULE REGISTERED]${colors.reset} https://${host}${path} ===> Service: ${targetService.serviceName}:${targetService.port}`);
  }

  route(incomingHost, incomingPath) {
    const key = `${incomingHost}:${incomingPath}`;
    const target = this.rules.get(key);

    if (!target) {
      console.log(`[INGRESS L7] ${incomingHost}${incomingPath} -> ${colors.red}[404 Not Found] Tidak ada ingress rule yang cocok${colors.reset}`);
      return { status: 404 };
    }

    console.log(`[INGRESS L7 ROUTED] https://${incomingHost}${incomingPath} -> Forwarded to ClusterIP Service ${colors.green}[${target.serviceName}:${target.port}]${colors.reset}`);
    return { status: 200, target };
  }
}

// ==========================================
// TEST SCENARIOS
// ==========================================
async function runLab() {
  console.log(`${colors.bold}${colors.cyan}=== DEVOPS LAB: HELM TEMPLATING, ROLLBACK, & INGRESS ===${colors.reset}\n`);

  // 1. Ingress L7 Virtual Host Routing
  console.log('--- 1. INGRESS CONTROLLER LAYER-7 ROUTING ---');
  const ingress = new IngressControllerSimulator();
  ingress.addRule('shop.acme.com', '/', { serviceName: 'frontend-service', port: 80 });
  ingress.addRule('api.acme.com', '/v1', { serviceName: 'order-api-service', port: 3000 });
  ingress.addRule('api.acme.com', '/auth', { serviceName: 'auth-service', port: 4000 });

  console.log('\nUji Coba Pengiriman Traffic HTTP Ingress:');
  ingress.route('shop.acme.com', '/');
  ingress.route('api.acme.com', '/v1');
  ingress.route('api.acme.com', '/auth');
  ingress.route('unknown.acme.com', '/'); // 404 test

  // 2. Helm Lifecycle & Rollback Test
  console.log('\n--- 2. HELM RELEASE LIFECYCLE (UPGRADE & ROLLBACK) ---');
  const helm = new HelmEngineSimulator('acme-core-app');

  // Rilis v1.0.0
  const prodValuesV1 = {
    replicaCount: 3,
    image: { repository: 'acme/backend', tag: 'v1.0.0' },
    dbHost: 'db.prod.internal',
    dbPassword: 'SuperSecretProductionPass2026',
    resources: { requests: { memory: '128Mi' }, limits: { memory: '256Mi' } }
  };
  helm.upgradeRelease('order-backend', prodValuesV1);

  // Upgrade ke v2.0.0 (Bermasalah)
  const prodValuesV2 = {
    replicaCount: 5,
    image: { repository: 'acme/backend', tag: 'v2.0.0-buggy' },
    dbHost: 'db.prod.internal',
    dbPassword: 'SuperSecretProductionPass2026',
    resources: { requests: { memory: '256Mi' }, limits: { memory: '512Mi' } }
  };
  helm.upgradeRelease('order-backend', prodValuesV2);

  // Cetak riwayat rilis sebelum rollback
  helm.printHistory();

  // Terjadi insiden regresi di v2.0.0! Lakukan rollback instan ke Revisi #1
  helm.rollback('order-backend', 1);

  // Cetak riwayat akhir
  helm.printHistory();

  console.log(`${colors.bold}${colors.green}=== SEMUA SIMULASI HELM & INGRESS SELESAI DENGAN SUKSES ===${colors.reset}`);
}

runLab();
