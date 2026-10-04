/**
 * Dockerfile Layer Caching & Build Cache Invalidation Simulator
 * Hands-on Lab: BAB 03 - Module 01
 * 
 * Demonstrates:
 * 1. Step-by-step Docker Build Layer evaluation with SHA256 checksums.
 * 2. Cache Hit vs Cache Invalidation mechanics.
 * 3. Best Practice (Deps first) vs Anti-Pattern (Source code copied before npm ci).
 */

const crypto = require('crypto');

class DockerBuildEngine {
  constructor() {
    this.layerCache = new Map(); // layerHash -> { output, durationMs }
  }

  computeHash(previousLayerHash, instruction, fileContents = '') {
    return crypto
      .createHash('sha256')
      .update(previousLayerHash + instruction + fileContents)
      .digest('hex')
      .substring(0, 12);
  }

  async executeBuild(dockerfileSteps, buildContext) {
    console.log(`\n======================================================`);
    console.log(`🔨 EXECUTING DOCKER BUILD SEQUENCE`);
    console.log(`======================================================`);

    let currentHash = 'root-sha-0000';
    let cacheBroken = false;
    let totalBuildTimeMs = 0;

    for (let i = 0; i < dockerfileSteps.length; i++) {
      const step = dockerfileSteps[i];
      const stepNum = i + 1;
      const fileContent = step.watchFile ? (buildContext[step.watchFile] || '') : '';
      const layerHash = this.computeHash(currentHash, step.instruction, fileContent);

      if (!cacheBroken && this.layerCache.has(layerHash)) {
        console.log(`Step ${stepNum}/${dockerfileSteps.length} : ${step.instruction}`);
        console.log(`   ↳ ---> Using cache (${layerHash}) [0ms]`);
        currentHash = layerHash;
      } else {
        cacheBroken = true; // Invalidate all subsequent layers!
        console.log(`Step ${stepNum}/${dockerfileSteps.length} : ${step.instruction}`);
        console.log(`   ↳ ---> Running step (${layerHash})...`);
        const duration = step.executionTimeMs || 50;
        await new Promise(r => setTimeout(r, Math.min(duration, 100))); // Scaled simulation
        totalBuildTimeMs += duration;
        this.layerCache.set(layerHash, { instruction: step.instruction, durationMs: duration });
        currentHash = layerHash;
      }
    }

    console.log(`------------------------------------------------------`);
    console.log(`🎉 Successfully built image! Digest: sha256:${currentHash}`);
    console.log(`⏱️  Total Build Time: ${totalBuildTimeMs}ms`);
    console.log(`======================================================\n`);
    return { finalHash: currentHash, totalBuildTimeMs };
  }
}

// -----------------------------------------------------------------
// LAB SIMULATION
// -----------------------------------------------------------------
async function runLab() {
  console.log(`======================================================`);
  console.log(`🏗️  DOCKER BUILD CACHE OPTIMIZATION LAB`);
  console.log(`======================================================\n`);

  const engine = new DockerBuildEngine();

  // Optimal Dockerfile Step Definition
  const optimalDockerfile = [
    { instruction: 'FROM node:20-alpine', executionTimeMs: 200 },
    { instruction: 'WORKDIR /app', executionTimeMs: 20 },
    { instruction: 'COPY package*.json ./', watchFile: 'package.json', executionTimeMs: 40 },
    { instruction: 'RUN npm ci --only=production', executionTimeMs: 1200 }, // Heavy step!
    { instruction: 'COPY . .', watchFile: 'src/index.js', executionTimeMs: 60 },
    { instruction: 'CMD ["node", "src/index.js"]', executionTimeMs: 10 }
  ];

  const buildContext = {
    'package.json': '{"name":"api","version":"1.0.0","dependencies":{"express":"4.18"}}',
    'src/index.js': 'console.log("Hello from Docker!");'
  };

  // 1. Initial Cold Build (No cache available)
  console.log(`--- TEST 1: COLD BUILD (FIRST TIME RUN) ---`);
  await engine.executeBuild(optimalDockerfile, buildContext);

  // 2. Second Build (Zero code changes -> 100% Cache Hit)
  console.log(`--- TEST 2: RE-BUILD WITHOUT ANY CODE CHANGES ---`);
  await engine.executeBuild(optimalDockerfile, buildContext);

  // 3. Third Build (Developer edits only src/index.js, package.json untouched)
  console.log(`--- TEST 3: DEVELOPER EDITS ONLY 'src/index.js' ---`);
  buildContext['src/index.js'] = 'console.log("Hello from Docker V2 with updated route!");';
  await engine.executeBuild(optimalDockerfile, buildContext);

  // 4. Contrast with Anti-Pattern Dockerfile (COPY . . before npm ci)
  console.log(`--- TEST 4: ANTI-PATTERN DEMO (COPY . . BEFORE npm ci) ---`);
  const antiPatternEngine = new DockerBuildEngine();
  const badDockerfile = [
    { instruction: 'FROM node:20-alpine', executionTimeMs: 200 },
    { instruction: 'WORKDIR /app', executionTimeMs: 20 },
    { instruction: 'COPY . .', watchFile: 'src/index.js', executionTimeMs: 60 }, // Bad placement!
    { instruction: 'RUN npm ci --only=production', executionTimeMs: 1200 }, // Re-runs every time!
    { instruction: 'CMD ["node", "src/index.js"]', executionTimeMs: 10 }
  ];

  console.log(`Cold build bad Dockerfile:`);
  await antiPatternEngine.executeBuild(badDockerfile, buildContext);

  console.log(`Re-building bad Dockerfile after 1 line edit in src/index.js:`);
  buildContext['src/index.js'] = 'console.log("Hello from Docker V3!");';
  await antiPatternEngine.executeBuild(badDockerfile, buildContext);

  console.log(`🎉 Docker Layer Cache Simulator Completed Successfully!`);
}

runLab();
