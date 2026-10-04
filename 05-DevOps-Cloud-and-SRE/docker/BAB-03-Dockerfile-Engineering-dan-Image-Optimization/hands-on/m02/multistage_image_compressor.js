/**
 * Multi-Stage Build & Image Optimization Simulator
 * Hands-on Lab: BAB 03 - Module 02
 * 
 * Demonstrates:
 * 1. Single-Stage Build (Bloated with compilers, SDK, devDependencies).
 * 2. Multi-Stage Build (Extracts only compiled binary to minimal Scratch / Distroless).
 * 3. Comparative Metric Analytics: Size, Pull Time, and CVE Vulnerability Reduction.
 */

class SingleStageImageBuilder {
  static build(appName) {
    console.log(`\n🔨 [Single-Stage] Building ${appName} with standard monolithic Dockerfile...`);
    const layers = [
      { name: 'Base OS & Compiler SDK (golang:1.22)', sizeMb: 820, cveCount: 28 },
      { name: 'Git, gcc, make, build-essential', sizeMb: 240, cveCount: 14 },
      { name: 'Go module dependencies cache', sizeMb: 110, cveCount: 0 },
      { name: 'Source code & intermediate object files', sizeMb: 35, cveCount: 0 },
      { name: 'Final compiled binary (/bin/server)', sizeMb: 14, cveCount: 0 }
    ];

    const totalSizeMb = layers.reduce((acc, l) => acc + l.sizeMb, 0);
    const totalCves = layers.reduce((acc, l) => acc + l.cveCount, 0);

    return {
      type: 'Single-Stage Monolithic',
      layers,
      totalSizeMb,
      totalCves,
      hasShell: true,
      hasPackageInstaller: true
    };
  }
}

class MultiStageImageBuilder {
  static build(appName) {
    console.log(`\n🚀 [Multi-Stage] Building ${appName} using Multi-Stage Distroless / Scratch pattern...`);
    console.log(`   ↳ [Stage 1: builder] Compiling static binary in temporary container...`);
    console.log(`   ↳ [Stage 2: release] Copying only /bin/server into 'FROM scratch'...`);

    const finalLayers = [
      { name: 'Base Image (scratch - empty root)', sizeMb: 0.0, cveCount: 0 },
      { name: 'CA Root Certificates (/etc/ssl/certs)', sizeMb: 0.2, cveCount: 0 },
      { name: 'Static Compiled Binary (/bin/server)', sizeMb: 14.0, cveCount: 0 }
    ];

    const totalSizeMb = finalLayers.reduce((acc, l) => acc + l.sizeMb, 0);
    const totalCves = finalLayers.reduce((acc, l) => acc + l.cveCount, 0);

    return {
      type: 'Multi-Stage Scratch/Distroless',
      layers: finalLayers,
      totalSizeMb,
      totalCves,
      hasShell: false,
      hasPackageInstaller: false
    };
  }
}

class ImageMetricsAnalyzer {
  static compare(singleStage, multiStage) {
    // Network pull calculation over a typical 100 Mbps (12.5 MB/s) cloud link
    const bandwidthMbps = 12.5;
    const singlePullSec = (singleStage.totalSizeMb / bandwidthMbps).toFixed(1);
    const multiPullSec = (multiStage.totalSizeMb / bandwidthMbps).toFixed(2);
    const sizeReductionPercent = ((1 - (multiStage.totalSizeMb / singleStage.totalSizeMb)) * 100).toFixed(1);

    console.log(`\n========================================================================================`);
    console.log(`📊 DOCKER IMAGE OPTIMIZATION BENCHMARK REPORT`);
    console.log(`========================================================================================`);
    console.log(`Metric                   | Single-Stage Monolithic | Multi-Stage Distroless/Scratch | Benefit`);
    console.log(`-------------------------|-------------------------|--------------------------------|-----------------`);
    console.log(`Total Image Size         | ${singleStage.totalSizeMb.toString().padEnd(19)} MB | ${multiStage.totalSizeMb.toFixed(1).toString().padEnd(26)} MB | ${sizeReductionPercent}% Shrunk!`);
    console.log(`Registry Pull Time       | ~${singlePullSec.toString().padEnd(18)} sec | ~${multiPullSec.toString().padEnd(25)} sec | ${((singlePullSec / multiPullSec)).toFixed(0)}x Faster!`);
    console.log(`Known OS Vulnerabilities | ${singleStage.totalCves.toString().padEnd(20)} CVEs | ${multiStage.totalCves.toString().padEnd(27)} CVEs | 100% Eliminated`);
    console.log(`Shell Interpreter (/bin) | ${singleStage.hasShell ? 'YES (/bin/bash, sh)' : 'NO'}                   | ${multiStage.hasShell ? 'YES' : 'NONE (Hardened No-Shell)'}     | Zero RCE Shell`);
    console.log(`Package Manager (apt/apk)| ${singleStage.hasPackageInstaller ? 'YES (apt-get)' : 'NO'}                   | ${multiStage.hasPackageInstaller ? 'YES' : 'NONE (Immutable)'}            | Attack Immunity`);
    console.log(`========================================================================================\n`);
  }
}

// -----------------------------------------------------------------
// LAB SIMULATION
// -----------------------------------------------------------------
async function runLab() {
  console.log(`======================================================`);
  console.log(`🔬 MULTI-STAGE DOCKER COMPRESSION & HARDENING LAB`);
  console.log(`======================================================`);

  const single = SingleStageImageBuilder.build('Payment-Gateway-API');
  const multi = MultiStageImageBuilder.build('Payment-Gateway-API');

  ImageMetricsAnalyzer.compare(single, multi);

  console.log(`🎉 Multi-Stage Image Compression Lab Completed Successfully!`);
}

runLab();
