/**
 * SRE Engine: SLI, SLO, Error Budget Tracking, Burn Rate & Feature Freeze Simulator
 * Hands-on Lab: BAB 10 - Module 01
 * 
 * Demonstrates:
 * 1. SLI Calculation: Good Events / Total Events.
 * 2. Error Budget Tracking: Total allowance based on SLO (e.g. 99.9%).
 * 3. Multi-Burn-Rate Alerting: Detecting rapid budget depletion (Burn Rate > 14.4x).
 * 4. Policy Enforcement: Automated Feature Freeze when Error Budget hits 0%.
 */

class ServiceLevelObjectiveEngine {
  constructor(serviceName, sloTarget = 0.999, windowTotalRequests = 10000) {
    this.serviceName = serviceName;
    this.sloTarget = sloTarget; // e.g. 99.9%
    this.windowTotalRequests = windowTotalRequests;
    
    // Mathematical error budget pool
    this.allowedErrors = Math.floor(windowTotalRequests * (1 - sloTarget)); // e.g. 10 errors per 10k requests
    this.totalRequests = 0;
    this.goodRequests = 0;
    this.badRequests = 0;

    this.featureFreezeActive = false;
  }

  recordBatch(good, bad) {
    this.totalRequests += (good + bad);
    this.goodRequests += good;
    this.badRequests += bad;

    const currentSli = (this.goodRequests / this.totalRequests);
    const consumedBudget = this.badRequests;
    const remainingBudgetPercent = Math.max(0, ((this.allowedErrors - consumedBudget) / this.allowedErrors) * 100);

    // Burn Rate Calculation: (Actual Error Rate) / (Allowed Error Rate: 1 - SLO)
    const currentErrorRate = this.badRequests / this.totalRequests;
    const allowedErrorRate = 1 - this.sloTarget;
    const burnRate = (currentErrorRate / allowedErrorRate);

    console.log(`\n------------------------------------------------------`);
    console.log(`📊 SRE METRICS REPORT: [${this.serviceName}]`);
    console.log(`------------------------------------------------------`);
    console.log(`Total Requests Processed: ${this.totalRequests} (Good: ${this.goodRequests}, Bad: ${this.badRequests})`);
    console.log(`Current SLI Availability: ${(currentSli * 100).toFixed(3)}% (Target SLO: ${(this.sloTarget * 100).toFixed(3)}%)`);
    console.log(`Error Budget Pool: ${this.allowedErrors} allowed errors | Consumed: ${consumedBudget} errors`);
    console.log(`Remaining Error Budget: ${remainingBudgetPercent.toFixed(1)}%`);
    console.log(`Calculated Burn Rate: ${burnRate.toFixed(2)}x`);

    // Evaluate Alerts & Policies
    this.evaluatePolicies(burnRate, remainingBudgetPercent);
  }

  evaluatePolicies(burnRate, remainingBudgetPercent) {
    // 1. High Burn Rate Alert (Consuming budget at alarming speed)
    if (burnRate >= 14.4) {
      console.error(`🚨 [CRITICAL ALERT: SEV-1] HighErrorBudgetBurnRate firing!`);
      console.error(`   Burn rate is ${burnRate.toFixed(2)}x normal speed! >2% of 30-day budget will burn in 1 hour.`);
      console.error(`   ↳ PagerDuty notification dispatched to On-Call SRE & Engineering Lead.`);
    } else if (burnRate > 5.0) {
      console.warn(`⚠️  [WARNING ALERT] Elevated Error Budget Burn Rate: ${burnRate.toFixed(2)}x`);
    } else {
      console.log(`🟢 [HEALTHY] Burn rate is normal (${burnRate.toFixed(2)}x).`);
    }

    // 2. Feature Freeze Policy Enforcement
    if (remainingBudgetPercent <= 0) {
      this.featureFreezeActive = true;
      console.error(`\n🔒 [POLICY TRIGGERED: FEATURE FREEZE ACTIVE]`);
      console.error(`   Error budget for '${this.serviceName}' is 100% DEPLETED!`);
      console.error(`   ↳ Action: ArgoCD/GitHub Actions pipeline has automatically BLOCKED all new feature releases.`);
      console.error(`   ↳ Engineering team is mandated to work strictly on Reliability, Bugs, & Architecture hardening.`);
    } else {
      this.featureFreezeActive = false;
      console.log(`🚀 [DEPLOYMENT STATUS] Permitted. Features may be released with standard canary safeguards.`);
    }
  }

  attemptFeatureRelease(featureName) {
    console.log(`\n📦 Attempting to release new feature: '${featureName}'...`);
    if (this.featureFreezeActive) {
      console.error(`❌ RELEASE REJECTED: Feature Freeze is currently in effect due to depleted Error Budget!`);
      return false;
    }
    console.log(`✅ RELEASE APPROVED: Error budget healthy. Feature '${featureName}' deployed to production.`);
    return true;
  }
}

// -----------------------------------------------------------------
// LAB SIMULATION
// -----------------------------------------------------------------
async function runLab() {
  console.log(`======================================================`);
  console.log(`📈 SRE RELIABILITY & ERROR BUDGET SIMULATOR`);
  console.log(`Target SLO: 99.9% Availability (Budget = 0.1% = 10 errors per 10,000 reqs)`);
  console.log(`======================================================`);

  const sre = new ServiceLevelObjectiveEngine('Payment-Gateway-API', 0.999, 10000);

  // Phase 1: Normal healthy operations (3000 good requests, 1 transient error)
  console.log(`\n>>> PHASE 1: STABLE OPERATIONS <<<`);
  sre.recordBatch(3000, 1);
  sre.attemptFeatureRelease('One-Click-Checkout-v2');

  // Phase 2: Upstream Partner Degradation (Minor spike: 2000 requests, 3 errors)
  console.log(`\n>>> PHASE 2: MINOR UPSTREAM DEGRADATION <<<`);
  sre.recordBatch(2000, 3);

  // Phase 3: Severe Outage / High Burn Rate Spike (1000 requests, 12 errors -> exceeds allowed budget of 10!)
  console.log(`\n>>> PHASE 3: SEVERE OUTAGE & BUDGET EXHAUSTION <<<`);
  sre.recordBatch(1000, 12);

  // Phase 4: Developer attempts to release risky new feature during freeze
  console.log(`\n>>> PHASE 4: ATTEMPTING FEATURE RELEASE DURING OUTAGE <<<`);
  sre.attemptFeatureRelease('Crypto-Payment-Integration');

  console.log(`\n🎉 SRE Error Budget & Reliability Simulator Lab Complete!`);
}

runLab();
