/**
 * Docker Compose V2 Dependency Graph & Healthcheck Orchestrator Simulator
 * Hands-on Lab: BAB 06 - Module 01
 * 
 * Demonstrates:
 * 1. The Race Condition bug: Simple depends_on without health condition.
 * 2. Compose V2 Startup Ordering: depends_on with condition: service_healthy.
 * 3. Topological sort and deterministic multi-service lifecycle management.
 */

class MockComposeService {
  constructor(name, options = {}) {
    this.name = name;
    this.dependsOn = options.dependsOn || {}; // serviceName -> condition ('service_healthy'|'started')
    this.requiresHealth = options.requiresHealth || false;
    this.healthAttemptsNeeded = options.healthAttemptsNeeded || 1;
    this.currentHealthAttempts = 0;
    this.status = 'STOPPED'; // STOPPED, STARTING, HEALTHY, RUNNING, FAILED
  }

  async probeHealth() {
    this.currentHealthAttempts++;
    console.log(`🩺 [Healthcheck: ${this.name}] Running probe attempt ${this.currentHealthAttempts}/${this.healthAttemptsNeeded}...`);
    if (this.currentHealthAttempts >= this.healthAttemptsNeeded) {
      this.status = 'HEALTHY';
      console.log(`✅ [Service: ${this.name}] Status transitioned to: [HEALTHY]`);
      return true;
    }
    console.log(`⏳ [Service: ${this.name}] Not yet ready (Booting DB tables)...`);
    return false;
  }
}

class ComposeOrchestrator {
  constructor(name) {
    this.name = name;
    this.services = new Map();
  }

  registerService(service) {
    this.services.set(service.name, service);
  }

  // Demonstration 1: Naive Startup (Race Condition Failure)
  async runNaiveStartup() {
    console.log(`\n======================================================`);
    console.log(`❌ TEST 1: NAIVE COMPOSE STARTUP (RACE CONDITION DEMO)`);
    console.log(`======================================================`);

    const db = this.services.get('postgres');
    const api = this.services.get('api-backend');

    console.log(`[Compose] Starting postgres container...`);
    db.status = 'STARTING';

    console.log(`[Compose] Simple 'depends_on: [postgres]' satisfied (PID is created).`);
    console.log(`[Compose] Starting api-backend immediately...`);
    api.status = 'STARTING';

    console.log(`⚡ [api-backend] Attempting TCP connection to postgres:5432...`);
    console.error(`💥 [CRASH] Fatal Error: connect ECONNREFUSED 172.20.0.2:5432!`);
    console.error(`   ↳ Database is still replaying WAL logs and not listening on socket yet!`);
    console.error(`   ↳ Container 'api-backend' exited with Exit Code 1.\n`);
    api.status = 'FAILED';
  }

  // Demonstration 2: Synchronized Healthcheck Startup
  async runSynchronizedStartup() {
    console.log(`======================================================`);
    console.log(`✅ TEST 2: SYNCHRONIZED COMPOSE V2 (CONDITION: SERVICE_HEALTHY)`);
    console.log(`======================================================\n`);

    const db = this.services.get('postgres');
    const api = this.services.get('api-backend');
    const nginx = this.services.get('nginx');

    db.status = 'STARTING';
    db.currentHealthAttempts = 0;
    console.log(`[Compose] Starting container 'postgres'...`);

    // Hold API until DB is healthy
    console.log(`⏳ [Compose Dependency Gate] 'api-backend' is waiting for 'postgres' to become HEALTHY...`);

    while (db.status !== 'HEALTHY') {
      await new Promise(r => setTimeout(r, 80));
      await db.probeHealth();
    }

    // Now start API
    console.log(`\n🚀 [Compose Dependency Gate] Condition satisfied! Starting 'api-backend'...`);
    api.status = 'RUNNING';
    console.log(`⚡ [api-backend] Connecting to postgres:5432...`);
    console.log(`✅ [api-backend] Connected successfully to Database! Listening on port 3000.`);

    // Now start Nginx
    console.log(`\n🚀 [Compose] Starting 'nginx' reverse proxy...`);
    nginx.status = 'RUNNING';
    console.log(`✅ [nginx] Proxying public port 80 ──> api-backend:3000.`);

    console.log(`\n------------------------------------------------------`);
    console.log(`📊 FINAL COMPOSE SERVICE STATUS MATRIX:`);
    console.log(`------------------------------------------------------`);
    for (const [name, s] of this.services.entries()) {
      console.log(`   🟢 [${s.status.padEnd(8)}] Service: ${name}`);
    }
    console.log(`------------------------------------------------------\n`);
  }
}

// -----------------------------------------------------------------
// LAB SIMULATION
// -----------------------------------------------------------------
async function runLab() {
  console.log(`======================================================`);
  console.log(`🐙 DOCKER COMPOSE V2 DEPENDENCY ENGINE SIMULATOR`);
  console.log(`======================================================`);

  const orchestrator = new ComposeOrchestrator('FinBank-Core');

  const postgres = new MockComposeService('postgres', {
    requiresHealth: true,
    healthAttemptsNeeded: 3 // Needs 3 probes to be ready
  });

  const api = new MockComposeService('api-backend', {
    dependsOn: { postgres: 'service_healthy' }
  });

  const nginx = new MockComposeService('nginx', {
    dependsOn: { 'api-backend': 'started' }
  });

  orchestrator.registerService(postgres);
  orchestrator.registerService(api);
  orchestrator.registerService(nginx);

  // 1. Simulate the bug
  await orchestrator.runNaiveStartup();

  // 2. Simulate the fix
  await orchestrator.runSynchronizedStartup();

  console.log(`🎉 Docker Compose Dependency Engine Lab Completed Successfully!`);
}

runLab();
