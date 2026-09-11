/**
 * ArgoCD GitOps Reconciler & Canary Rollout Simulator
 * Hands-on Lab: BAB 07 - Module 02
 * 
 * Demonstrates:
 * 1. GitOps Reconciler: Pull model desired state vs live cluster state diffing.
 * 2. Self-Healing: Instant rollback when manual drift occurs (kubectl edit injection).
 * 3. Canary Rollout: Traffic split progression (10% -> 50% -> 100%) with automated health analysis.
 */

class MockGitRepository {
  constructor() {
    this.commits = [];
    this.headCommit = null;
    this.manifests = new Map();
  }

  commit(sha, author, manifests) {
    this.manifests = new Map(Object.entries(manifests));
    this.headCommit = { sha, author, timestamp: new Date().toISOString() };
    this.commits.push(this.headCommit);
    console.log(`[Git] New commit pushed: ${sha} by ${author}`);
  }

  getHeadManifests() {
    return new Map(this.manifests);
  }
}

class MockK8sCluster {
  constructor() {
    this.resources = new Map();
    this.trafficMetrics = { totalRequests: 0, error5xxCount: 0 };
  }

  apply(resource) {
    this.resources.set(resource.id, { ...resource, updatedAt: Date.now() });
    console.log(`[K8s Cluster] Applied resource: ${resource.kind}/${resource.id} (Replicas: ${resource.replicas}, Image: ${resource.image})`);
  }

  delete(id) {
    if (this.resources.has(id)) {
      this.resources.delete(id);
      console.log(`[K8s Cluster] Pruned resource: ${id}`);
    }
  }

  // Inject manual drift (simulating unauthorized 'kubectl edit' command)
  simulateManualDrift(id, patch) {
    if (this.resources.has(id)) {
      const res = this.resources.get(id);
      Object.assign(res, patch);
      console.log(`⚠️  [UNAUTHORIZED DRIFT] Someone ran manual kubectl patch on ${id}:`, patch);
    }
  }

  getLiveState() {
    return new Map(this.resources);
  }
}

class ArgoCDReconciler {
  constructor(gitRepo, cluster, options = { autoHeal: true, prune: true }) {
    this.gitRepo = gitRepo;
    this.cluster = cluster;
    this.options = options;
  }

  reconcile() {
    console.log(`\n🔄 [ArgoCD Loop] Evaluating Desired State vs Live Cluster State...`);
    const desired = this.gitRepo.getHeadManifests();
    const live = this.cluster.getLiveState();

    let driftDetected = false;

    // 1. Check for missing or drifted resources
    for (const [id, desiredRes] of desired.entries()) {
      const liveRes = live.get(id);

      if (!liveRes) {
        console.log(`📢 [OutOfSync] Resource ${id} missing in cluster. Syncing...`);
        this.cluster.apply(desiredRes);
        driftDetected = true;
      } else {
        // Compare attributes
        const diffs = [];
        if (liveRes.replicas !== desiredRes.replicas) diffs.push(`replicas (${liveRes.replicas} != ${desiredRes.replicas})`);
        if (liveRes.image !== desiredRes.image) diffs.push(`image (${liveRes.image} != ${desiredRes.image})`);

        if (diffs.length > 0) {
          console.log(`⚠️  [OutOfSync] Drift detected on ${id}: ${diffs.join(', ')}`);
          if (this.options.autoHeal) {
            console.log(`🛡️  [Self-Heal] Auto-healing ${id} to match Git desired state.`);
            this.cluster.apply(desiredRes);
          }
          driftDetected = true;
        }
      }
    }

    // 2. Check for resources deleted in Git (Prune)
    if (this.options.prune) {
      for (const [id] of live.entries()) {
        if (!desired.has(id)) {
          console.log(`🧹 [Prune] Resource ${id} removed from Git. Deleting from cluster...`);
          this.cluster.delete(id);
          driftDetected = true;
        }
      }
    }

    if (!driftDetected) {
      console.log(`✅ [Synced] Cluster state is 100% HEALTHY and MATCHES Git repository.`);
    }
  }
}

class ArgoRolloutCanarySimulator {
  constructor(serviceName, oldImage, newImage) {
    this.serviceName = serviceName;
    this.oldImage = oldImage;
    this.newImage = newImage;
    this.trafficWeight = 0; // % routed to newImage
    this.status = 'INITIAL';
  }

  async executeRollout(simulateError = false) {
    console.log(`\n======================================================`);
    console.log(`🐥 STARTING ARGO CANARY ROLLOUT FOR: ${this.serviceName}`);
    console.log(`Stable: ${this.oldImage} ──> Target: ${this.newImage}`);
    console.log(`======================================================`);

    const steps = [10, 25, 50, 100];

    for (const stepWeight of steps) {
      this.trafficWeight = stepWeight;
      console.log(`\n[Rollout Step] Shifting traffic: ${stepWeight}% to Canary (${this.newImage}), ${100 - stepWeight}% to Stable`);

      console.log(`[Analysis] Running Prometheus Metric Query: sum(rate(http_5xx_errors[1m])) / sum(rate(http_requests[1m]))...`);
      await new Promise(r => setTimeout(r, 150));

      // Simulate metric evaluation
      const errorRate = (simulateError && stepWeight >= 50) ? 0.08 : 0.001;
      console.log(`[Analysis Result] Error Rate: ${(errorRate * 100).toFixed(2)}% (Threshold <= 1.00%)`);

      if (errorRate > 0.01) {
        console.error(`🚨 [ABORT] Metric analysis failed! Error rate exceeds threshold.`);
        console.log(`⏪ [Auto-Rollback] Argo Rollout immediately reverting traffic 100% to Stable (${this.oldImage}).`);
        this.trafficWeight = 0;
        this.status = 'ROLLED_BACK';
        return false;
      }

      console.log(`✅ [Step Passed] Metrics healthy. Proceeding to next step.`);
    }

    this.status = 'PROMOTED';
    console.log(`\n🎉 [Rollout Complete] Canary version ${this.newImage} fully promoted to 100% traffic!`);
    return true;
  }
}

async function runLab() {
  const git = new MockGitRepository();
  const k8s = new MockK8sCluster();
  const argo = new ArgoCDReconciler(git, k8s, { autoHeal: true, prune: true });

  // 1. Initial State in Git
  git.commit('c011a9f', 'devops-lead@company.com', {
    'deployment-order-service': { id: 'deployment-order-service', kind: 'Deployment', replicas: 3, image: 'app/order:v1.0.0' },
    'service-order': { id: 'service-order', kind: 'Service', replicas: 1, image: 'none' }
  });

  // Reconcile initial cluster
  argo.reconcile();

  // 2. Simulate unauthorized manual drift in Kubernetes cluster
  console.log(`\n--- TEST CASE 1: MANUAL CLUSTER DRIFT INJECTION ---`);
  k8s.simulateManualDrift('deployment-order-service', { replicas: 10 });
  // ArgoCD periodic reconciliation loop runs
  argo.reconcile();

  // 3. Simulate Git update & Pruning
  console.log(`\n--- TEST CASE 2: GIT COMMIT & DEPRECATED SERVICE PRUNING ---`);
  git.commit('d820b41', 'platform-engineer@company.com', {
    'deployment-order-service': { id: 'deployment-order-service', kind: 'Deployment', replicas: 5, image: 'app/order:v1.1.0' }
    // Note: service-order removed in Git to trigger prune
  });
  argo.reconcile();

  // 4. Simulate Argo Rollouts Canary Traffic with Health Analysis
  console.log(`\n--- TEST CASE 3: CANARY PROGRESSIVE DELIVERY ---`);
  const rollout = new ArgoRolloutCanarySimulator('order-service', 'app/order:v1.1.0', 'app/order:v2.0.0');
  await rollout.executeRollout(false);

  // 5. Simulate Canary Rollback on High Error Rate
  console.log(`\n--- TEST CASE 4: AUTOMATED ROLLBACK ON METRIC DEGRADATION ---`);
  const buggyRollout = new ArgoRolloutCanarySimulator('order-service', 'app/order:v2.0.0', 'app/order:v2.1.0-buggy');
  await buggyRollout.executeRollout(true);
}

runLab();
