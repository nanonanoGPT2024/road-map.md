/**
 * CI/CD Pipeline Automation Engine Simulator
 * Hands-on Lab: BAB 07 - Module 01
 * 
 * Simulates a modern declarative multi-stage CI/CD pipeline (Lint, Test, SAST, Build, Staging Deploy, Prod Approval).
 */

const { EventEmitter } = require('events');

class PipelineStep {
  constructor(name, runnerFn, dependsOn = []) {
    this.name = name;
    this.runnerFn = runnerFn;
    this.dependsOn = dependsOn;
    this.status = 'PENDING'; // PENDING, RUNNING, SUCCESS, FAILED, SKIPPED
    this.durationMs = 0;
    this.logs = [];
  }

  async execute(context) {
    this.status = 'RUNNING';
    const start = Date.now();
    try {
      await this.runnerFn(context, (log) => this.logs.push(`[${this.name}] ${log}`));
      this.status = 'SUCCESS';
    } catch (err) {
      this.status = 'FAILED';
      this.logs.push(`[${this.name}] ERROR: ${err.message}`);
      throw err;
    } finally {
      this.durationMs = Date.now() - start;
    }
  }
}

class PipelineRunner extends EventEmitter {
  constructor(name) {
    super();
    this.name = name;
    this.steps = new Map();
    this.context = {
      commitSha: 'a4b1c2e',
      branch: 'main',
      artifacts: {},
      environment: {}
    };
  }

  addStep(name, runnerFn, dependsOn = []) {
    this.steps.set(name, new PipelineStep(name, runnerFn, dependsOn));
    return this;
  }

  async run() {
    console.log(`\n======================================================`);
    console.log(`🚀 TRIGGERING CI/CD PIPELINE: ${this.name}`);
    console.log(`Commit: ${this.context.commitSha} | Branch: ${this.context.branch}`);
    console.log(`======================================================\n`);

    const completed = new Set();
    const failed = new Set();

    while (completed.size + failed.size < this.steps.size) {
      const readySteps = [];

      for (const [name, step] of this.steps.entries()) {
        if (step.status === 'PENDING') {
          const dependenciesMet = step.dependsOn.every(dep => completed.has(dep));
          const hasFailedDep = step.dependsOn.some(dep => failed.has(dep));

          if (hasFailedDep) {
            step.status = 'SKIPPED';
            failed.add(name);
            console.log(`⚠️  [SKIP] Step "${name}" skipped due to upstream failure.`);
          } else if (dependenciesMet) {
            readySteps.push(step);
          }
        }
      }

      if (readySteps.length === 0) {
        break; // No more steps can run
      }

      // Execute ready steps in parallel
      await Promise.all(readySteps.map(async (step) => {
        console.log(`⏳ [START] Executing: ${step.name}...`);
        try {
          await step.execute(this.context);
          completed.add(step.name);
          console.log(`✅ [PASS] ${step.name} completed in ${step.durationMs}ms`);
        } catch (err) {
          failed.add(step.name);
          console.error(`❌ [FAIL] ${step.name} failed: ${err.message}`);
        }
      }));
    }

    this.printSummary(completed, failed);
  }

  printSummary(completed, failed) {
    console.log(`\n------------------------------------------------------`);
    console.log(`📊 PIPELINE EXECUTION SUMMARY`);
    console.log(`------------------------------------------------------`);
    for (const [name, step] of this.steps.entries()) {
      const icon = step.status === 'SUCCESS' ? '✅' : step.status === 'FAILED' ? '❌' : '⚠️';
      console.log(`${icon} [${step.status.padEnd(7)}] ${name.padEnd(20)} (${step.durationMs}ms)`);
      if (step.logs.length > 0) {
        step.logs.forEach(l => console.log(`    ↳ ${l}`));
      }
    }
    console.log(`------------------------------------------------------`);
    if (failed.size > 0) {
      console.log(`❌ Pipeline Status: FAILED (${failed.size} errors)`);
    } else {
      console.log(`🎉 Pipeline Status: SUCCESS (All stages passed!)`);
    }
    console.log(`------------------------------------------------------\n`);
  }
}

// -------------------------------------------------------------
// DEMO PIPELINE SETUP
// -------------------------------------------------------------
async function runLab() {
  const pipeline = new PipelineRunner('Enterprise-Web-App-CI-CD');

  // Stage 1: Parallel Lint & SAST Scan
  pipeline.addStep('lint-code', async (ctx, log) => {
    log('Running ESLint & Prettier checks on /src...');
    await new Promise(r => setTimeout(r, 120));
    log('0 errors, 0 warnings found.');
  });

  pipeline.addStep('sast-security-scan', async (ctx, log) => {
    log('Running Semgrep / SonarQube static vulnerability scan...');
    await new Promise(r => setTimeout(r, 150));
    log('Dependency vulnerability check passed: Clean.');
  });

  // Stage 2: Unit & Integration Tests (Depends on Lint)
  pipeline.addStep('unit-test', async (ctx, log) => {
    log('Executing Jest suite: 42 test cases...');
    await new Promise(r => setTimeout(r, 180));
    log('Tests passed: 42/42. Coverage: 89.4% (Threshold >= 80%).');
    ctx.artifacts.testReport = 'coverage/lcov.info';
  }, ['lint-code']);

  // Stage 3: Docker Multi-Stage Build & Image Signing
  pipeline.addStep('build-and-push-image', async (ctx, log) => {
    log('Building Docker image: myregistry.io/app:v1.4.2...');
    await new Promise(r => setTimeout(r, 220));
    log('Image digest: sha256:7f83b1657ff1fc53b92dc...');
    log('Signing container image with Cosign keyless signature.');
    ctx.artifacts.dockerImage = 'myregistry.io/app:v1.4.2';
  }, ['unit-test', 'sast-security-scan']);

  // Stage 4: Deploy to Staging Cluster
  pipeline.addStep('deploy-staging', async (ctx, log) => {
    log(`Applying Kubernetes manifest to namespace: 'staging'...`);
    await new Promise(r => setTimeout(r, 160));
    log(`Deployed version ${ctx.artifacts.dockerImage} successfully.`);
  }, ['build-and-push-image']);

  // Stage 5: Automated Smoke & E2E Tests on Staging
  pipeline.addStep('staging-smoke-tests', async (ctx, log) => {
    log('Running curl healthcheck on https://staging.internal.net/healthz...');
    await new Promise(r => setTimeout(r, 100));
    log('HTTP Status: 200 OK. Latency: 24ms.');
  }, ['deploy-staging']);

  // Stage 6: Production Deployment Gate (Requires Approval)
  pipeline.addStep('deploy-production', async (ctx, log) => {
    log('Automated Canary Rollout initialized: 10% traffic routing.');
    await new Promise(r => setTimeout(r, 200));
    log('Error budget verified: 0.00% 5xx errors detected.');
    log('Promoting to 100% stable release.');
  }, ['staging-smoke-tests']);

  await pipeline.run();
}

runLab();
