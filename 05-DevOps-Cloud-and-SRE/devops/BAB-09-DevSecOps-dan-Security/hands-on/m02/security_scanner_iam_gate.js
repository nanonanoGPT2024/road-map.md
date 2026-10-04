/**
 * DevSecOps Scanner & Kubernetes Admission Controller Simulator
 * Hands-on Lab: BAB 09 - Module 02
 * 
 * Demonstrates:
 * 1. Trivy-style Container CVE Vulnerability Scanner with CI exit code gating.
 * 2. Kyverno / OPA Gatekeeper Admission Controller Simulator.
 * 3. Enforcement of Pod Security Standards (Non-Root, No-Privileged, Resource Limits, Immutable Tags).
 */

class MockTrivyScanner {
  constructor() {
    // Mock CVE Vulnerability Database
    this.cveDatabase = {
      'node:14-alpine': [
        { cve: 'CVE-2023-26159', pkg: 'follow-redirects', severity: 'CRITICAL', fixed: true },
        { cve: 'CVE-2022-0778', pkg: 'openssl', severity: 'HIGH', fixed: true },
        { cve: 'CVE-2021-36159', pkg: 'apk-tools', severity: 'LOW', fixed: false }
      ],
      'node:20-alpine-hardened': [
        { cve: 'CVE-2024-11111', pkg: 'dummy-lib', severity: 'LOW', fixed: false }
      ]
    };
  }

  scanImage(imageTag) {
    console.log(`\n🔍 [Trivy Scanner] Scanning container image: ${imageTag}...`);
    const vulnerabilities = this.cveDatabase[imageTag] || [];

    const summary = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 };
    vulnerabilities.forEach(v => {
      summary[v.severity] = (summary[v.severity] || 0) + 1;
    });

    console.log(`+-------------------------------------------------------------+`);
    console.log(`| CVE ID         | Package          | Severity | Fixed?       |`);
    console.log(`+-------------------------------------------------------------+`);
    if (vulnerabilities.length === 0) {
      console.log(`| No vulnerabilities detected! Image is clean.               |`);
    } else {
      vulnerabilities.forEach(v => {
        console.log(`| ${v.cve.padEnd(14)} | ${v.pkg.padEnd(16)} | ${v.severity.padEnd(8)} | ${v.fixed ? 'Yes (Patched)' : 'No (Unfixed)'} |`);
      });
    }
    console.log(`+-------------------------------------------------------------+`);
    console.log(`Total Findings: ${summary.CRITICAL} Critical, ${summary.HIGH} High, ${summary.LOW} Low\n`);

    return { vulnerabilities, summary };
  }

  evaluateCIGate(scanResult, maxCritical = 0, maxHigh = 0) {
    if (scanResult.summary.CRITICAL > maxCritical) {
      console.error(`❌ [CI Security Gate FAILED] Found ${scanResult.summary.CRITICAL} CRITICAL CVEs! (Threshold: ${maxCritical})`);
      return false;
    }
    if (scanResult.summary.HIGH > maxHigh) {
      console.error(`❌ [CI Security Gate FAILED] Found ${scanResult.summary.HIGH} HIGH CVEs! (Threshold: ${maxHigh})`);
      return false;
    }
    console.log(`✅ [CI Security Gate PASSED] Vulnerability scan satisfies security compliance policy.`);
    return true;
  }
}

class KubernetesAdmissionController {
  constructor() {
    this.policies = [
      {
        id: 'disallow-latest-tag',
        name: 'Immutability Check: Dilarang menggunakan tag :latest',
        validate: (pod) => {
          for (const c of pod.spec.containers) {
            if (c.image.endsWith(':latest') || !c.image.includes(':')) {
              return `Container '${c.name}' uses mutable image tag '${c.image}'. Explicit semantic tag or SHA digest required.`;
            }
          }
          return null;
        }
      },
      {
        id: 'require-run-as-non-root',
        name: 'Pod Security Check: Wajib runAsNonRoot',
        validate: (pod) => {
          const podSec = pod.spec.securityContext || {};
          if (!podSec.runAsNonRoot && (!podSec.runAsUser || podSec.runAsUser === 0)) {
            return `Pod '${pod.metadata.name}' must have securityContext.runAsNonRoot: true or runAsUser > 0!`;
          }
          return null;
        }
      },
      {
        id: 'disallow-privileged',
        name: 'Privilege Check: Dilarang privileged container & privilege escalation',
        validate: (pod) => {
          for (const c of pod.spec.containers) {
            const sec = c.securityContext || {};
            if (sec.privileged) {
              return `Container '${c.name}' requests privileged mode which is strictly forbidden!`;
            }
            if (sec.allowPrivilegeEscalation !== false) {
              return `Container '${c.name}' must explicitly set allowPrivilegeEscalation: false!`;
            }
          }
          return null;
        }
      },
      {
        id: 'require-resource-limits',
        name: 'Governance Check: Wajib menentukan CPU & Memory Limits',
        validate: (pod) => {
          for (const c of pod.spec.containers) {
            const res = c.resources || {};
            if (!res.limits || !res.limits.cpu || !res.limits.memory) {
              return `Container '${c.name}' is missing required CPU/Memory resource limits!`;
            }
          }
          return null;
        }
      }
    ];
  }

  validateAdmission(pod) {
    console.log(`\n🛡️  [Validating Admission Webhook] Evaluating Pod: '${pod.metadata.name}'...`);
    const violations = [];

    for (const policy of this.policies) {
      const errorMsg = policy.validate(pod);
      if (errorMsg) {
        violations.push({ policy: policy.name, error: errorMsg });
      }
    }

    if (violations.length > 0) {
      console.error(`🚨 [ADMISSION REJECTED] Pod '${pod.metadata.name}' violated ${violations.length} policy rules:`);
      violations.forEach(v => {
        console.error(`   ❌ [${v.policy}]`);
        console.error(`      ↳ Reason: ${v.error}`);
      });
      return false;
    }

    console.log(`🎉 [ADMISSION ALLOWED] Pod '${pod.metadata.name}' complies 100% with Cluster Security Governance!`);
    return true;
  }
}

// -----------------------------------------------------------------
// LAB SIMULATION
// -----------------------------------------------------------------
async function runLab() {
  console.log(`======================================================`);
  console.log(`🛡️  DEVSECOPS PIPELINE & ADMISSION GOVERNANCE LAB`);
  console.log(`======================================================`);

  // PART 1: Trivy Vulnerability Scanning in CI
  const trivy = new MockTrivyScanner();

  console.log(`--- CASE 1: SCANNING VULNERABLE LEGACY IMAGE ---`);
  const legacyScan = trivy.scanImage('node:14-alpine');
  trivy.evaluateCIGate(legacyScan, 0, 0);

  console.log(`\n--- CASE 2: SCANNING HARDENED PRODUCTION IMAGE ---`);
  const hardenedScan = trivy.scanImage('node:20-alpine-hardened');
  trivy.evaluateCIGate(hardenedScan, 0, 0);

  // PART 2: Kubernetes Admission Webhook Policy Enforcement
  const gatekeeper = new KubernetesAdmissionController();

  console.log(`\n--- CASE 3: ADMISSION CONTROL OF INSECURE POD MANIFEST ---`);
  const insecurePod = {
    metadata: { name: 'insecure-billing-worker' },
    spec: {
      containers: [
        {
          name: 'worker',
          image: 'myregistry.io/billing:latest', // Violates immutability
          securityContext: {
            privileged: true, // Violates privileged check
            allowPrivilegeEscalation: true
          }
          // Missing runAsNonRoot and resource limits
        }
      ]
    }
  };
  gatekeeper.validateAdmission(insecurePod);

  console.log(`\n--- CASE 4: ADMISSION CONTROL OF HARDENED PRODUCTION POD ---`);
  const securePod = {
    metadata: { name: 'secure-billing-worker' },
    spec: {
      securityContext: {
        runAsNonRoot: true,
        runAsUser: 10001
      },
      containers: [
        {
          name: 'worker',
          image: 'myregistry.io/billing:v2.4.1', // Immutable semver
          securityContext: {
            privileged: false,
            allowPrivilegeEscalation: false,
            readOnlyRootFilesystem: true
          },
          resources: {
            requests: { cpu: '100m', memory: '128Mi' },
            limits: { cpu: '500m', memory: '512Mi' }
          }
        }
      ]
    }
  };
  gatekeeper.validateAdmission(securePod);

  console.log(`\n🎉 DevSecOps & Governance Lab Completed Successfully!`);
}

runLab();
