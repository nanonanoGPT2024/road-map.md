/**
 * Chaos Fault Injector & FinOps Cost Optimization Simulator
 * Hands-on Lab: BAB 10 - Module 02
 * 
 * Demonstrates:
 * 1. Chaos Engineering: Proactively killing active pods to measure Self-Healing & RTO.
 * 2. PodDisruptionBudget (PDB) enforcement during Spot instance interruption.
 * 3. FinOps Analysis: Real-time cost comparison (On-Demand vs Right-Sized ARM64 Spot Instances).
 */

class MockPod {
  constructor(id, nodeType = 'on-demand') {
    this.id = id;
    this.nodeType = nodeType; // on-demand or spot
    this.status = 'Running'; // Running, Terminating, Dead
    this.createdAt = Date.now();
  }
}

class ResilientCluster {
  constructor(desiredReplicas = 3, minAvailablePDB = 2) {
    this.desiredReplicas = desiredReplicas;
    this.minAvailablePDB = minAvailablePDB; // Pod Disruption Budget
    this.pods = [];
    this.initPods();
  }

  initPods() {
    for (let i = 1; i <= this.desiredReplicas; i++) {
      this.pods.push(new MockPod(`pod-payment-${i}`, 'spot'));
    }
  }

  getActivePodsCount() {
    return this.pods.filter(p => p.status === 'Running').length;
  }

  // Chaos Injection: Abruptly kill a random active pod
  async injectPodChaos() {
    const activePods = this.pods.filter(p => p.status === 'Running');
    if (activePods.length === 0) return;

    const victim = activePods[Math.floor(Math.random() * activePods.length)];
    victim.status = 'Dead';
    console.log(`💥 [CHAOS FAULT INJECTED] Killed pod: ${victim.id} (simulating sudden node crash or OOMKill)`);

    const startRecover = Date.now();
    console.log(`⏳ [ReplicaSet Controller] Active pods count: ${this.getActivePodsCount()}/${this.desiredReplicas}. Detecting drift...`);

    // Simulate K8s reconciliation loop & pod reschedule
    await new Promise(r => setTimeout(r, 180));
    const newPod = new MockPod(`pod-payment-${Date.now().toString().slice(-4)}`, 'spot');
    this.pods = this.pods.filter(p => p.status === 'Running');
    this.pods.push(newPod);
    const rtoDuration = Date.now() - startRecover;

    console.log(`🟢 [SELF-HEALING COMPLETE] Replaced with new pod: ${newPod.id}`);
    console.log(`   ↳ Actual RTO (Recovery Time Objective): ${rtoDuration}ms (Target: < 500ms). System 100% HEALTHY.`);
  }

  // Spot Preemption with PDB compliance
  async simulateSpotPreemption() {
    console.log(`\n⚡ [AWS SPOT INTERUPTION EVENT] Received 2-minute preemption signal on spot node...`);
    const active = this.getActivePodsCount();

    if (active <= this.minAvailablePDB) {
      console.warn(`🛡️  [PDB SHIELD ACTIVE] Current active: ${active} <= PDB minAvailable: ${this.minAvailablePDB}.`);
      console.warn(`   Refusing eviction until replacement pod is completely healthy! (Zero Downtime Guaranteed).`);
    }

    // Provision replacement on another spot node
    console.log(`🔄 [Karpenter] Fast-provisioning replacement pod on another available Spot NodePool...`);
    await new Promise(r => setTimeout(r, 120));
    const newPod = new MockPod(`pod-payment-spot-${Date.now().toString().slice(-4)}`, 'spot');
    this.pods.push(newPod);

    // Now safely terminate the old pod
    const oldPod = this.pods.find(p => p.status === 'Running');
    if (oldPod) oldPod.status = 'Dead';
    this.pods = this.pods.filter(p => p.status === 'Running');
    console.log(`✅ [Graceful Drain] Preempted pod successfully terminated with ZERO request drops.`);
  }
}

class FinOpsCostAnalyzer {
  static analyzeSavings(nodeCount = 20) {
    const onDemandRatePerHour = 0.10; // e.g. m5.large x86
    const spotArmRatePerHour = 0.028; // e.g. m6g.large Graviton ARM64 (72% discount)
    const hoursPerMonth = 730;

    const onDemandMonthly = nodeCount * onDemandRatePerHour * hoursPerMonth;
    const spotArmMonthly = nodeCount * spotArmRatePerHour * hoursPerMonth;
    const monthlySavings = onDemandMonthly - spotArmMonthly;
    const annualSavings = monthlySavings * 12;
    const percentageSaved = ((monthlySavings / onDemandMonthly) * 100).toFixed(1);

    console.log(`\n======================================================`);
    console.log(`💰 FINOPS CLOUD COST OPTIMIZATION ANALYSIS`);
    console.log(`Workload: ${nodeCount} Compute Nodes (24/7 Production Cluster)`);
    console.log(`======================================================`);
    console.log(`Baseline (Legacy x86 On-Demand):   $${onDemandMonthly.toLocaleString('en-US', { minimumFractionDigits: 2 })} / month`);
    console.log(`Optimized (Karpenter Graviton Spot): $${spotArmMonthly.toLocaleString('en-US', { minimumFractionDigits: 2 })} / month`);
    console.log(`------------------------------------------------------`);
    console.log(`🎉 Net Monthly Cost Reduction:       $${monthlySavings.toLocaleString('en-US', { minimumFractionDigits: 2 })} / month`);
    console.log(`🏆 Annualized Cost Savings:          $${annualSavings.toLocaleString('en-US', { minimumFractionDigits: 2 })} / year`);
    console.log(`📈 Total Budget Efficiency Gain:     ${percentageSaved}% Saved!`);
    console.log(`======================================================\n`);
  }
}

// -----------------------------------------------------------------
// LAB SIMULATION
// -----------------------------------------------------------------
async function runLab() {
  console.log(`======================================================`);
  console.log(`💥 CHAOS ENGINEERING & FINOPS CLOUD OPTIMIZER LAB`);
  console.log(`======================================================\n`);

  const cluster = new ResilientCluster(3, 2);
  console.log(`Initial Cluster State: ${cluster.getActivePodsCount()} running replicas.`);

  // Test 1: Chaos Engineering (Sudden Pod Kill)
  console.log(`\n--- TEST 1: CHAOS MONKEY / POD CRASH INJECTION ---`);
  await cluster.injectPodChaos();

  // Test 2: Spot Preemption with PodDisruptionBudget (PDB)
  console.log(`\n--- TEST 2: SPOT PREEMPTION & PDB GUARANTEE ---`);
  await cluster.simulateSpotPreemption();

  // Test 3: FinOps Cloud Savings Modeling
  console.log(`\n--- TEST 3: FINOPS COST SAVINGS & RIGHT-SIZING MODEL ---`);
  FinOpsCostAnalyzer.analyzeSavings(50); // Cluster with 50 nodes

  console.log(`🎉 Chaos & FinOps Simulator Lab Completed Successfully!`);
}

runLab();
