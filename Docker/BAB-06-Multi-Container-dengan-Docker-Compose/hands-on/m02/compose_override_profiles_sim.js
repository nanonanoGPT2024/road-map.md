/**
 * Docker Compose Multi-File Merge & Profiles Simulator
 * Hands-on Lab: BAB 06 - Module 02
 * 
 * Demonstrates:
 * 1. Deep Merge of Base Compose + Environment Overrides (Dev vs Prod).
 * 2. Selective Service Activation using Compose Profiles (`--profile monitoring`).
 * 3. Secret Injection without plaintext password exposure.
 */

function deepMerge(target, source) {
  const output = { ...target };
  for (const [key, value] of Object.entries(source)) {
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      output[key] = deepMerge(target[key] || {}, value);
    } else if (Array.isArray(value)) {
      output[key] = Array.from(new Set([...(target[key] || []), ...value]));
    } else {
      output[key] = value;
    }
  }
  return output;
}

class ComposeProfileSimulator {
  constructor(mergedConfig) {
    this.config = mergedConfig;
  }

  resolveActiveServices(activeProfiles = []) {
    console.log(`\n======================================================`);
    console.log(`🔍 EVALUATING COMPOSE PROFILES (Active: [${activeProfiles.join(', ')}])`);
    console.log(`======================================================`);

    const activeList = [];
    const skippedList = [];

    for (const [serviceName, spec] of Object.entries(this.config.services)) {
      const serviceProfiles = spec.profiles || [];

      if (serviceProfiles.length === 0) {
        // Core service (No profile constraint) -> ALWAYS RUN
        activeList.push({ name: serviceName, reason: 'Core Service (Default)' });
      } else {
        // Profiled service -> Only run if at least one profile matches
        const hasMatch = serviceProfiles.some(p => activeProfiles.includes(p));
        if (hasMatch) {
          activeList.push({ name: serviceName, reason: `Profile Match: [${serviceProfiles.join(', ')}]` });
        } else {
          skippedList.push({ name: serviceName, reason: `Requires profile: [${serviceProfiles.join(', ')}]` });
        }
      }
    }

    console.log(`🚀 ACTIVE SERVICES TO START:`);
    activeList.forEach(s => console.log(`   🟢 [START] ${s.name.padEnd(16)} (${s.reason})`));

    console.log(`\n⏸️  SKIPPED SERVICES (SAVING RAM):`);
    skippedList.forEach(s => console.log(`   ⚪ [SKIP ] ${s.name.padEnd(16)} (${s.reason})`));

    return activeList;
  }
}

// -----------------------------------------------------------------
// LAB SIMULATION
// -----------------------------------------------------------------
async function runLab() {
  console.log(`======================================================`);
  console.log(`🐙 COMPOSE OVERRIDES & PROFILES ENGINE LAB`);
  console.log(`======================================================\n`);

  // 1. BASE SPECIFICATION (compose.yaml)
  const baseConfig = {
    services: {
      database: {
        image: 'postgres:16-alpine',
        environment: { POSTGRES_DB: 'app_db' },
        volumes: ['pgdata:/var/lib/postgresql/data']
      },
      api: {
        image: 'my-app:latest',
        environment: { DB_HOST: 'database' }
      },
      prometheus: {
        image: 'prom/prometheus:latest',
        profiles: ['monitoring']
      },
      pgadmin: {
        image: 'dpage/pgadmin4:latest',
        profiles: ['tools']
      }
    },
    volumes: { pgdata: {} }
  };

  // 2. DEV OVERRIDE (compose.dev.yaml)
  const devOverride = {
    services: {
      api: {
        volumes: ['./backend:/usr/src/app'], // Bind mount for hot-reload
        ports: ['3000:3000'],
        environment: { DEBUG: 'true', LOG_LEVEL: 'debug' }
      },
      database: {
        ports: ['5432:5432'] // Expose port for local DBeaver connection
      }
    }
  };

  // 3. PROD OVERRIDE (compose.prod.yaml)
  const prodOverride = {
    services: {
      api: {
        image: 'myregistry.io/finbank/api:v2.4.0', // Immutable release tag
        restart: 'unless-stopped',
        ports: ['127.0.0.1:3000:3000'], // Restricted binding
        environment: { NODE_ENV: 'production', LOG_LEVEL: 'error' },
        deploy: { resources: { limits: { memory: '1024M', cpus: '2.0' } } }
      },
      database: {
        restart: 'unless-stopped',
        deploy: { resources: { limits: { memory: '2048M' } } }
      }
    }
  };

  // TEST 1: Simulate 'docker compose -f compose.yaml -f compose.dev.yaml config'
  console.log(`--- TEST 1: GENERATING MERGED DEV SPECIFICATION ---`);
  const mergedDev = deepMerge(baseConfig, devOverride);
  console.log(`[Dev Merged] API Volumes:`, mergedDev.services.api.volumes);
  console.log(`[Dev Merged] API Environment:`, mergedDev.services.api.environment);

  // TEST 2: Simulate 'docker compose -f compose.yaml -f compose.prod.yaml config'
  console.log(`\n--- TEST 2: GENERATING MERGED PROD SPECIFICATION ---`);
  const mergedProd = deepMerge(baseConfig, prodOverride);
  console.log(`[Prod Merged] API Image:`, mergedProd.services.api.image);
  console.log(`[Prod Merged] API Deploy Limits:`, mergedProd.services.api.deploy.resources.limits);
  console.log(`[Prod Merged] API Ports (Hardened Localhost):`, mergedProd.services.api.ports);

  // TEST 3: Profiles Evaluation - Default (No Profile)
  console.log(`\n--- TEST 3: EXECUTING DEFAULT STARTUP (docker compose up -d) ---`);
  const sim = new ComposeProfileSimulator(mergedDev);
  sim.resolveActiveServices([]); // No profile passed

  // TEST 4: Profiles Evaluation - With Monitoring Profile
  console.log(`\n--- TEST 4: EXECUTING WITH MONITORING (docker compose --profile monitoring up -d) ---`);
  sim.resolveActiveServices(['monitoring']);

  console.log(`\n🎉 Compose Overrides & Profiles Lab Completed Successfully!`);
}

runLab();
