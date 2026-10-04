/**
 * Seccomp Syscall Filter, Trivy Scan, & Cosign Signing Simulator
 * Hands-on Lab: BAB 07 - Module 02
 * 
 * Demonstrates:
 * 1. Supply Chain Gate: Trivy image scanning with severity gating.
 * 2. Cryptographic Provenance: Cosign digital signature verification.
 * 3. Kernel Runtime Sandbox: Seccomp syscall interception & blocking.
 */

const crypto = require('crypto');

class MockTrivyScanner {
  static scan(imageName, imageTag) {
    console.log(`\n🔍 [Trivy Scanner] Inspecting image: ${imageName}:${imageTag}...`);
    
    // Simulate vulnerability database check
    const isVulnerable = imageTag === 'v1.0.0-legacy';
    const cves = isVulnerable ? [
      { id: 'CVE-2023-44487', pkg: 'nghttp2', severity: 'CRITICAL', title: 'HTTP/2 Rapid Reset Attack' },
      { id: 'CVE-2023-38545', pkg: 'curl', severity: 'HIGH', title: 'SOCKS5 Heap Buffer Overflow' }
    ] : [
      { id: 'CVE-2024-99999', pkg: 'dummy-lib', severity: 'LOW', title: 'Minor doc typo' }
    ];

    const criticalCount = cves.filter(c => c.severity === 'CRITICAL').length;
    const highCount = cves.filter(c => c.severity === 'HIGH').length;

    console.log(`+------------------+------------+----------+--------------------------------+`);
    console.log(`| CVE ID           | Package    | Severity | Title                          |`);
    console.log(`+------------------+------------+----------+--------------------------------+`);
    cves.forEach(c => {
      console.log(`| ${c.id.padEnd(16)} | ${c.pkg.padEnd(10)} | ${c.severity.padEnd(8)} | ${c.title.padEnd(30)} |`);
    });
    console.log(`+------------------+------------+----------+--------------------------------+`);

    const passed = criticalCount === 0;
    if (!passed) {
      console.error(`❌ [CI GATE BLOCKED] Image contains ${criticalCount} CRITICAL vulnerabilities! Build failed.`);
    } else {
      console.log(`✅ [CI GATE PASSED] Zero CRITICAL vulnerabilities. Image approved for signing.`);
    }
    return { passed, cves };
  }
}

class CosignSignatureEngine {
  constructor() {
    const { publicKey, privateKey } = crypto.generateKeyPairSync('rsa', { modulusLength: 2048 });
    this.publicKey = publicKey;
    this.privateKey = privateKey;
  }

  signDigest(imageDigest) {
    console.log(`\n🔏 [Cosign Sign] Signing image digest: ${imageDigest.substring(0, 16)}...`);
    const sign = crypto.createSign('SHA256');
    sign.update(imageDigest);
    sign.end();
    const signature = sign.sign(this.privateKey, 'base64');
    console.log(`   ↳ Cryptographic Signature generated: ${signature.substring(0, 24)}...`);
    return signature;
  }

  verifySignature(imageDigest, signature) {
    console.log(`\n🛡️  [Cosign Verify] Verifying signature against public key...`);
    const verify = crypto.createVerify('SHA256');
    verify.update(imageDigest);
    verify.end();
    const isValid = verify.verify(this.publicKey, signature, 'base64');
    if (isValid) {
      console.log(`✅ [Signature Valid] Image integrity verified! Image was produced by authorized CI pipeline.`);
    } else {
      console.error(`🚨 [TAMPERED IMAGE] Signature verification failed! Refusing to run untrusted image.`);
    }
    return isValid;
  }
}

class SeccompSyscallFilter {
  constructor(disallowedSyscalls = ['ptrace', 'reboot', 'kexec_load', 'sys_chroot']) {
    this.disallowed = new Set(disallowedSyscalls);
  }

  invokeSyscall(containerName, syscallName) {
    console.log(`[${containerName}] Calling syscall: ${syscallName}()...`);
    if (this.disallowed.has(syscallName)) {
      console.error(`   🚫 [SECCOMP BLOCKED] Action: SECCOMP_RET_ERRNO (EPERM: Operation not permitted).`);
      console.error(`      ↳ Syscall '${syscallName}' is blacklisted by Seccomp profile!`);
      return false;
    }
    console.log(`   🟢 [SECCOMP ALLOWED] Syscall '${syscallName}' permitted by kernel.`);
    return true;
  }
}

// -----------------------------------------------------------------
// LAB SIMULATION
// -----------------------------------------------------------------
async function runLab() {
  console.log(`======================================================`);
  console.log(`🛡️  DOCKER SECCOMP, TRIVY SCAN & COSIGN LAB`);
  console.log(`======================================================`);

  // PART 1: Trivy Vulnerability Scanning in CI
  console.log(`\n--- PART 1: SUPPLY CHAIN SCANNING (TRIVY) ---`);
  // Test A: Vulnerable legacy image (Fails Gate)
  const legacyScan = MockTrivyScanner.scan('finbank-api', 'v1.0.0-legacy');
  
  // Test B: Hardened production image (Passes Gate)
  const secureScan = MockTrivyScanner.scan('finbank-api', 'v2.0.0-distroless');

  // PART 2: Cosign Digital Signing & Verification
  console.log(`\n--- PART 2: DIGITAL SIGNATURE VERIFICATION (COSIGN) ---`);
  const cosign = new CosignSignatureEngine();
  const imageDigest = 'sha256:7f83b1657ff1fc53b92dce1b34e5695a02476d0d2972985f0ef352669e7f7b3c';

  // Legitimate signing in CI
  const validSignature = cosign.signDigest(imageDigest);
  cosign.verifySignature(imageDigest, validSignature);

  // Attacker tampers image digest in registry
  const tamperedDigest = 'sha256:0000000000000000000000000000000000000000000000000000000000000000';
  cosign.verifySignature(tamperedDigest, validSignature);

  // PART 3: Seccomp Syscall Filtering in Kernel
  console.log(`\n--- PART 3: KERNEL SECCOMP FILTERING ---`);
  const seccomp = new SeccompSyscallFilter(['ptrace', 'reboot', 'kexec_load']);

  // Allowed legitimate application syscalls
  seccomp.invokeSyscall('order-api', 'read');
  seccomp.invokeSyscall('order-api', 'epoll_wait');
  seccomp.invokeSyscall('order-api', 'socket');

  // Malware attempts privilege escalation / debugger inspection
  console.log(`\nMalware attempts to inspect other processes via ptrace:`);
  seccomp.invokeSyscall('order-api', 'ptrace');

  console.log(`Malware attempts to crash host server via reboot:`);
  seccomp.invokeSyscall('order-api', 'reboot');

  console.log(`\n🎉 Seccomp, Trivy, & Cosign Security Lab Complete!`);
}

runLab();
