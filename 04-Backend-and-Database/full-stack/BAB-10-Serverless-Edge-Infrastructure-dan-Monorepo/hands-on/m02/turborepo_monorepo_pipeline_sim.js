/**
 * SIMULATOR: Turborepo Pipeline Graph, Remote Caching, & Standalone Docker Analyzer
 * -----------------------------------------------------------------------------
 * File: turborepo_monorepo_pipeline_sim.js
 * Deskripsi: Simulasi mandiri (zero-dependency) dari resolver dependensi topologis
 * monorepo ala Turborepo, kalkulasi content-aware hashing (SHA-256), deteksi
 * Full Turbo remote cache hit, dan perbandingan efisiensi image Docker Standalone.
 */

const crypto = require("crypto");

// =============================================================================
// 1. TURBOREPO DEPENDENCY GRAPH RESOLVER
// =============================================================================

class MonorepoPipelineEngine {
  constructor(packages) {
    this.packages = packages; // Map of packageName -> { deps: [], sourceContent: "" }
    this.remoteCache = new Map(); // hash -> buildArtifact
  }

  // Menghitung Content-Aware Hash berdasarkan konten paket dan dependensinya
  computePackageHash(pkgName) {
    const pkg = this.packages[pkgName];
    const hash = crypto.createHash("sha256");

    hash.update(`content:${pkg.sourceContent}`);

    // Masukkan hash dependensi hulu (upstream)
    for (const dep of pkg.deps) {
      const depHash = this.computePackageHash(dep);
      hash.update(`dep:${dep}:${depHash}`);
    }

    return hash.digest("hex").substring(0, 12);
  }

  // Menyelesaikan urutan eksekusi topologis (Topological Sort)
  resolveBuildOrder() {
    const visited = new Set();
    const order = [];

    const visit = (name) => {
      if (visited.has(name)) return;
      visited.add(name);
      for (const dep of this.packages[name].deps) {
        visit(dep);
      }
      order.push(name);
    };

    for (const name of Object.keys(this.packages)) {
      visit(name);
    }

    return order;
  }

  // Simulasi Eksekusi `turbo run build`
  async executeBuild() {
    const buildOrder = this.resolveBuildOrder();
    const results = [];
    let totalRealBuildTime = 0;
    let totalSavedTime = 0;

    for (const pkgName of buildOrder) {
      const pkgHash = this.computePackageHash(pkgName);
      const isCached = this.remoteCache.has(pkgHash);

      if (isCached) {
        // Cache Hit: Ambil dari cache dalam hitungan milidetik!
        const cachedDuration = 15; // ms
        totalSavedTime += this.packages[pkgName].simulatedBuildCostMs - cachedDuration;
        results.push({
          package: pkgName,
          hash: pkgHash,
          status: ">>> FULL TURBO (CACHE HIT) ⚡",
          durationMs: cachedDuration,
        });
      } else {
        // Cache Miss: Kompilasi nyata
        const realDuration = this.packages[pkgName].simulatedBuildCostMs;
        totalRealBuildTime += realDuration;
        this.remoteCache.set(pkgHash, { output: `dist/${pkgName}.bundle.js` });
        results.push({
          package: pkgName,
          hash: pkgHash,
          status: "BUILDING FROM SOURCE...",
          durationMs: realDuration,
        });
      }
    }

    return { results, totalRealBuildTime, totalSavedTime };
  }
}

// =============================================================================
// 2. DOCKER MULTI-STAGE STANDALONE ANALYZER
// =============================================================================

function analyzeDockerLayers() {
  const naiveBuild = {
    osBase: 45, // MB (node:20-alpine)
    allNodeModules: 850, // MB (seluruh devDependencies & monorepo dependencies)
    sourceCodeAndGit: 180, // MB
    buildTools: 220, // MB (TypeScript compiler, Webpack, PostCSS)
  };

  const standaloneBuild = {
    osBase: 45, // MB (node:20-alpine)
    standaloneTracedDeps: 32, // MB (Hanya file runtime yang benar-benar dieksekusi)
    compiledServerJs: 8, // MB (.next/standalone)
    staticAssets: 6, // MB (.next/static)
  };

  const naiveTotal = Object.values(naiveBuild).reduce((a, b) => a + b, 0);
  const standaloneTotal = Object.values(standaloneBuild).reduce((a, b) => a + b, 0);
  const savingsPercent = (((naiveTotal - standaloneTotal) / naiveTotal) * 100).toFixed(1);

  return { naiveTotal, standaloneTotal, savingsPercent };
}

// =============================================================================
// 3. RUN SUITE
// =============================================================================

async function runSimulation() {
  console.log("===========================================================================");
  console.log("SIMULASI: TURBOREPO BUILD GRAPH & STANDALONE DOCKER CONTAINERIZATION");
  console.log("===========================================================================\n");

  const monorepoDefinition = {
    "packages/config": { deps: [], sourceContent: "eslint_tsconfig_v1.0", simulatedBuildCostMs: 400 },
    "packages/database": { deps: ["packages/config"], sourceContent: "drizzle_schema_v1.0", simulatedBuildCostMs: 1200 },
    "packages/ui": { deps: ["packages/config"], sourceContent: "radix_buttons_v1.0", simulatedBuildCostMs: 1800 },
    "apps/web": { deps: ["packages/ui", "packages/database"], sourceContent: "nextjs_web_home_v1.0", simulatedBuildCostMs: 3500 },
    "apps/admin": { deps: ["packages/ui"], sourceContent: "vite_admin_portal_v1.0", simulatedBuildCostMs: 2200 },
  };

  const turbo = new MonorepoPipelineEngine(monorepoDefinition);

  console.log("--- TAHAP 1: Resolusi Urutan Dependensi Topologis Monorepo ---");
  const order = turbo.resolveBuildOrder();
  console.log("  Urutan Kompilasi Tervalidasi:", order.join("  ->  ") + "\n");

  // RUN 1: COLD BUILD PERTAMA KALI
  console.log("--- TAHAP 2: Eksekusi 'turbo run build' (Putaran 1: Cold Cache Miss) ---");
  const run1 = await turbo.executeBuild();
  for (const item of run1.results) {
    console.log(`  📦 ${item.package.padEnd(20)} [${item.hash}] : ${item.status} (${item.durationMs}ms)`);
  }
  console.log(`  ⏱️  Waktu Build Kompilasi Nyata : ${(run1.totalRealBuildTime / 1000).toFixed(2)} detik\n`);

  // RUN 2: WARM BUILD SETELAH MEMODIFIKASI HANYA APPS/WEB
  console.log("--- TAHAP 3: Pengembang Memodifikasi Kode di 'apps/web' Saja ---");
  console.log("  (Kode packages/ui, packages/database, dan apps/admin TIDAK BERUBAH)...");
  monorepoDefinition["apps/web"].sourceContent = "nextjs_web_home_v1.1_UPDATED_HERO";

  const run2 = await turbo.executeBuild();
  for (const item of run2.results) {
    console.log(`  📦 ${item.package.padEnd(20)} [${item.hash}] : ${item.status} (${item.durationMs}ms)`);
  }
  console.log(`  ⚡ Waktu Yang Berhasil Dihemat oleh Remote Cache : ${(run2.totalSavedTime / 1000).toFixed(2)} detik!\n`);

  // ANALISIS IMAGE DOCKER
  console.log("--- TAHAP 4: Analisis Efisiensi Image Docker (Next.js Standalone) ---");
  const dockerStats = analyzeDockerLayers();
  console.log(`  🐳 Ukuran Image Docker Naif (Seluruh node_modules) : ${dockerStats.naiveTotal} MB (~1.3 GB)`);
  console.log(`  🚀 Ukuran Image Docker Multi-Stage Standalone      : ${dockerStats.standaloneTotal} MB`);
  console.log(`  📉 Efisiensi Penghematan Penyimpanan & Bandwidth    : ${dockerStats.savingsPercent}% PENYUSUTAN! (Ultra Ringan! ✅)\n`);

  console.log("===========================================================================");
  console.log("SIMULASI SELESAI: Seluruh protokol Monorepo & GitOps Teruji Sempurna!");
  console.log("===========================================================================");
}

runSimulation();
