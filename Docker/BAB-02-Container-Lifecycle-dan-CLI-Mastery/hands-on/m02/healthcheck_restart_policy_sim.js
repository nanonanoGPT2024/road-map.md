/**
 * Docker Healthcheck Engine & Restart Policy Simulator
 * Hands-on Lab: BAB 02 - Module 02
 * 
 * Demonstrates:
 * 1. Healthcheck State Transitions: starting -> healthy -> unhealthy.
 * 2. Probe retry logic & start-period grace window.
 * 3. Restart Policy Logic: 'no', 'always', 'unless-stopped', 'on-failure'.
 */

class HealthcheckEngine {
  constructor(options = {}) {
    this.intervalMs = options.intervalMs || 100;
    this.timeoutMs = options.timeoutMs || 50;
    this.retries = options.retries || 3;
    this.startPeriodMs = options.startPeriodMs || 200;

    this.status = 'starting'; // starting, healthy, unhealthy
    this.failureCount = 0;
    this.startTime = Date.now();
    this.history = [];
  }

  evaluateProbe(isProbePassing) {
    const elapsed = Date.now() - this.startTime;
    const inStartPeriod = elapsed < this.startPeriodMs;

    if (isProbePassing) {
      this.failureCount = 0;
      this.status = 'healthy';
      this.history.push({ elapsed, result: 'SUCCESS', status: this.status });
      console.log(`🩺 [Healthcheck] Probe SUCCEEDED (${elapsed}ms). Status: HEALTHY`);
    } else {
      if (inStartPeriod) {
        console.log(`⏳ [Healthcheck] Probe FAILED during start-period (${elapsed}ms < ${this.startPeriodMs}ms). Ignored.`);
        this.history.push({ elapsed, result: 'FAIL_IGNORED', status: this.status });
      } else {
        this.failureCount++;
        console.warn(`⚠️  [Healthcheck] Probe FAILED! Failure count: ${this.failureCount}/${this.retries}`);
        if (this.failureCount >= this.retries) {
          this.status = 'unhealthy';
        }
        this.history.push({ elapsed, result: 'FAIL', status: this.status });
      }
    }
    return this.status;
  }
}

class RestartPolicyEngine {
  static evaluate(policy, exitCode, wasStoppedManually = false) {
    console.log(`\nEvaluating Restart Policy: '${policy}' | Exit Code: ${exitCode} | Manual Stop: ${wasStoppedManually}`);

    switch (policy) {
      case 'no':
        return { shouldRestart: false, reason: "Policy 'no' never restarts." };

      case 'always':
        return { shouldRestart: true, reason: "Policy 'always' unconditionally restarts." };

      case 'unless-stopped':
        if (wasStoppedManually) {
          return { shouldRestart: false, reason: "Policy 'unless-stopped' honors manual docker stop." };
        }
        return { shouldRestart: true, reason: "Policy 'unless-stopped' restarts unexpected failure." };

      case 'on-failure':
        if (exitCode !== 0) {
          return { shouldRestart: true, reason: "Policy 'on-failure' restarts non-zero exit codes." };
        }
        return { shouldRestart: false, reason: "Policy 'on-failure' does NOT restart clean exit 0." };

      default:
        return { shouldRestart: false, reason: "Unknown policy" };
    }
  }
}

// -----------------------------------------------------------------
// LAB SIMULATION
// -----------------------------------------------------------------
async function runLab() {
  console.log(`======================================================`);
  console.log(`🩺 DOCKER HEALTHCHECK & RESTART POLICY LAB`);
  console.log(`======================================================\n`);

  // PART 1: Healthcheck State Transitions
  console.log(`--- PART 1: HEALTHCHECK PROBING & RETRY ENGINE ---`);
  const hc = new HealthcheckEngine({
    intervalMs: 80,
    retries: 3,
    startPeriodMs: 150
  });

  console.log(`Initial Container Health: ${hc.status}`);

  // Step 1: Probe fails during start period (ignored)
  hc.evaluateProbe(false);
  await new Promise(r => setTimeout(r, 60));

  // Step 2: Probe succeeds after warm up -> healthy
  await new Promise(r => setTimeout(r, 100)); // past startPeriod
  hc.evaluateProbe(true);
  console.log(`Container Health after warmup: ${hc.status}`);

  // Step 3: Application encounters silent deadlock -> consecutive probe failures
  console.log(`\n[Sim] Injecting application deadlock (endpoints return 500)...`);
  hc.evaluateProbe(false); // fail 1
  hc.evaluateProbe(false); // fail 2
  hc.evaluateProbe(false); // fail 3 -> reaches retry threshold!

  console.log(`\nFinal Container Health Status: [${hc.status.toUpperCase()}]`);

  // PART 2: Restart Policies Evaluation Matrix
  console.log(`\n--- PART 2: RESTART POLICY DECISION MATRIX ---`);

  const testCases = [
    { policy: 'no', exitCode: 1, manual: false },
    { policy: 'on-failure', exitCode: 0, manual: false },
    { policy: 'on-failure', exitCode: 137, manual: false },
    { policy: 'unless-stopped', exitCode: 143, manual: true },
    { policy: 'unless-stopped', exitCode: 1, manual: false },
    { policy: 'always', exitCode: 0, manual: false }
  ];

  console.log(`+----------------+-----------+-------------+----------------+------------------------------------------+`);
  console.log(`| Policy         | Exit Code | Manual Stop | Should Restart | Reason                                   |`);
  console.log(`+----------------+-----------+-------------+----------------+------------------------------------------+`);
  testCases.forEach(tc => {
    const decision = RestartPolicyEngine.evaluate(tc.policy, tc.exitCode, tc.manual);
    console.log(`| ${tc.policy.padEnd(14)} | ${tc.exitCode.toString().padEnd(9)} | ${tc.manual.toString().padEnd(11)} | ${decision.shouldRestart.toString().padEnd(14)} | ${decision.reason.padEnd(40)} |`);
  });
  console.log(`+----------------+-----------+-------------+----------------+------------------------------------------+\n`);

  console.log(`🎉 Healthcheck & Restart Policy Lab Completed Successfully!`);
}

runLab();
