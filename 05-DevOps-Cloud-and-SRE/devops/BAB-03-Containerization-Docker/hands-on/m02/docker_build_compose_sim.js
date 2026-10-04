/**
 * Hands-on M02: Docker Layer Caching, Multi-Stage Sizing, & Compose Orchestrator Simulator
 * Mengilustrasikan konsep:
 * 1. Docker Build Layer Caching (Cache Hit vs Cache Invalidation)
 * 2. Perbandingan Ukuran Image Single-Stage vs Multi-Stage
 * 3. Docker Compose Dependency Graph & Healthcheck Wait
 *
 * Jalankan: node docker_build_compose_sim.js
 */

const crypto = require('crypto');

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
// 1. DOCKER LAYER CACHING ENGINE
// ==========================================
class DockerLayerBuildEngine {
  constructor() {
    this.layerCache = new Map(); // hash -> { layerId, durationMs }
  }

  calculateHash(instruction, fileContents = '') {
    return crypto.createHash('sha256').update(instruction + ':' + fileContents).digest('hex').substring(0, 12);
  }

  async build(dockerfileSteps, buildContext) {
    console.log(`${colors.cyan}[DOCKER BUILD] Memulai build image...${colors.reset}`);
    let isCacheValid = true;
    let totalTimeMs = 0;

    for (let i = 0; i < dockerfileSteps.length; i++) {
      const step = dockerfileSteps[i];
      const stepNum = i + 1;
      const fileData = buildContext[step.fileKey] || '';
      const layerHash = this.calculateHash(step.cmd, fileData);

      if (isCacheValid && this.layerCache.has(layerHash)) {
        console.log(`  Step ${stepNum}/${dockerfileSteps.length} : ${step.cmd} -> ${colors.green}[USING CACHE]${colors.reset} (0ms)`);
      } else {
        // Cache miss atau invalidated oleh layer sebelumnya
        isCacheValid = false;
        const simulatedWorkTime = step.durationMs || 100;
        totalTimeMs += simulatedWorkTime;
        await new Promise(r => setTimeout(r, Math.min(simulatedWorkTime, 200))); // Cap visual delay
        
        this.layerCache.set(layerHash, { layerId: layerHash, durationMs: simulatedWorkTime });
        console.log(`  Step ${stepNum}/${dockerfileSteps.length} : ${step.cmd} -> ${colors.yellow}[EXECUTED]${colors.reset} (${simulatedWorkTime}ms)`);
      }
    }

    console.log(`${colors.green}[BUILD FINISHED] Total waktu build: ${totalTimeMs}ms${colors.reset}\n`);
    return totalTimeMs;
  }
}

// ==========================================
// 2. DOCKER COMPOSE ORCHESTRATOR
// ==========================================
class DockerComposeSimulator {
  constructor() {
    this.services = [
      { name: 'postgres', healthReady: false, port: 5432, volume: 'pgdata_volume' },
      { name: 'redis', healthReady: false, port: 6379 },
      { name: 'web-api', dependsOn: ['postgres', 'redis'], port: 3000 }
    ];
  }

  async up() {
    console.log(`\n${colors.bold}${colors.magenta}=== [DOCKER COMPOSE UP -D] ORCHESTRATION ===${colors.reset}`);
    console.log(`[NETWORK CREATED] "app-tier-bridge" (Isolated Subnet: 172.28.0.0/16)`);
    console.log(`[VOLUME CREATED] "pgdata_volume" mounted to /var/lib/postgresql/data\n`);

    // 1. Start Infrastructure Services (DB & Redis)
    console.log(`[STARTING] postgres container...`);
    await new Promise(r => setTimeout(r, 200));
    console.log(`  -> postgres healthcheck: "pg_isready" PASS [HEALTHY]`);
    const pg = this.services.find(s => s.name === 'postgres');
    pg.healthReady = true;

    console.log(`[STARTING] redis container...`);
    await new Promise(r => setTimeout(r, 100));
    console.log(`  -> redis ping: "PONG" [HEALTHY]`);
    const redis = this.services.find(s => s.name === 'redis');
    redis.healthReady = true;

    // 2. Start Application Service after dependencies are healthy
    console.log(`\n[DEPENDENCY RESOLVED] Semua service upstream sehat. Memulai web-api...`);
    await new Promise(r => setTimeout(r, 150));
    console.log(`${colors.green}[WEB-API STARTED] Mendengarkan pada http://localhost:3000 (Terhubung ke Postgres:5432 & Redis:6379)${colors.reset}\n`);
  }
}

// ==========================================
// TEST SCENARIOS
// ==========================================
async function runLab() {
  console.log(`${colors.bold}${colors.cyan}=== DEVOPS LAB: DOCKER OPTIMIZATION & COMPOSE ===${colors.reset}\n`);

  const engine = new DockerLayerBuildEngine();

  // Definisi urutan Dockerfile optimal
  const optimalDockerfile = [
    { cmd: 'FROM node:20-alpine', fileKey: 'base', durationMs: 50 },
    { cmd: 'WORKDIR /app', fileKey: 'workdir', durationMs: 20 },
    { cmd: 'COPY package*.json ./', fileKey: 'pkgJson', durationMs: 40 },
    { cmd: 'RUN npm ci --production', fileKey: 'pkgJson', durationMs: 800 },
    { cmd: 'COPY . .', fileKey: 'srcCode', durationMs: 150 },
    { cmd: 'CMD ["node", "server.js"]', fileKey: 'cmd', durationMs: 10 }
  ];

  // Run 1: Build Pertama (Clean cache)
  console.log('--- BUILD 1: RUN PERTAMA (DARI NOL) ---');
  let context = {
    pkgJson: '{"name": "app", "version": "1.0.0", "dependencies": {"express": "^4.18"}}',
    srcCode: 'console.log("v1.0.0");'
  };
  await engine.build(optimalDockerfile, context);

  // Run 2: Hanya ubah file source code (package.json tetap sama)
  console.log('--- BUILD 2: MENGUBAH SOURCE CODE SAJA (TEST CACHE REUSE) ---');
  context.srcCode = 'console.log("v1.0.1 - Bugfix updated");'; // Source code berubah
  await engine.build(optimalDockerfile, context);

  // 2. Perbandingan Ukuran Multi-Stage Build
  console.log('--- PERBANDINGAN UKURAN IMAGE DOCKER ---');
  const imageComparisons = [
    { type: 'Single-Stage (node:20 full + devDependencies)', sizeMb: 1150, layers: 14, vulnerabilities: 42 },
    { type: 'Single-Stage (node:20-alpine standard)', sizeMb: 240, layers: 8, vulnerabilities: 9 },
    { type: 'Multi-Stage (Alpine builder + Alpine distroless runner)', sizeMb: 52, layers: 4, vulnerabilities: 0 }
  ];

  console.log('Image Profile\t\t\t\t\tSize\tLayers\tKnown CVEs');
  console.log('-----------------------------------------------------------------------------');
  imageComparisons.forEach(img => {
    console.log(`${img.type.padEnd(45)}\t${img.sizeMb}MB\t${img.layers}\t${img.vulnerabilities}`);
  });
  console.log('-----------------------------------------------------------------------------\n');

  // 3. Docker Compose Orchestration Test
  const compose = new DockerComposeSimulator();
  await compose.up();

  console.log(`${colors.bold}${colors.green}=== SEMUA PENGUJIAN DOCKER LAYER & COMPOSE SELESAI DENGAN SUKSES ===${colors.reset}`);
}

runLab();
