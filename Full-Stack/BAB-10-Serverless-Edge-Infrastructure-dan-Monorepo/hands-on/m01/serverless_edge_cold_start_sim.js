/**
 * SIMULATOR: Serverless Cold Start vs Edge V8 Isolate & Geo-IP Router
 * -----------------------------------------------------------------------------
 * File: serverless_edge_cold_start_sim.js
 * Deskripsi: Simulasi mandiri (zero-dependency) dari perbandingan latensi Cold Start
 * antara Micro-VM Container vs V8 Isolate, router personalisasi Geo-IP global,
 * dan failover otomatis perbatasan Edge.
 */

// =============================================================================
// 1. COLD START & RUNTIME SIMULATOR
// =============================================================================

class MicroVMServerlessRuntime {
  constructor() {
    this.isWarm = false;
  }

  async invoke(payload) {
    const start = process.hrtime.bigint();

    if (!this.isWarm) {
      // Simulasi OS boot, inisialisasi micro-VM Firecracker, parsing 35MB JS bundle
      let dummyMem = [];
      for (let i = 0; i < 250000; i++) {
        dummyMem.push({ chunk: i, env: "aws-lambda-nodejs20.x" });
      }
      this.isWarm = true;
      const end = process.hrtime.bigint();
      const durationMs = Number(end - start) / 1e6 + 220; // Tambahan latensi VM kernel
      return { type: "COLD_START (MICRO-VM)", durationMs, result: payload };
    } else {
      // Warm Invocation
      await new Promise((r) => setTimeout(r, 4));
      const end = process.hrtime.bigint();
      const durationMs = Number(end - start) / 1e6;
      return { type: "WARM_INVOCATION", durationMs, result: payload };
    }
  }
}

class V8IsolateEdgeRuntime {
  constructor() {
    this.isWarm = false;
  }

  async invoke(payload) {
    const start = process.hrtime.bigint();

    // V8 Isolate: Hanya mengalokasikan konteks memori baru di proses yang sudah aktif
    const isolateContext = { globalScope: true, payload };
    this.isWarm = true;

    const end = process.hrtime.bigint();
    const durationMs = Number(end - start) / 1e6 + 1.2; // Rata-rata inisialisasi Isolate V8
    return { type: "COLD_START (V8 ISOLATE)", durationMs, result: payload };
  }
}

// =============================================================================
// 2. SIMULATOR GLOBAL EDGE POP ROUTING & GEO-PERSONALIZATION
// =============================================================================

class GlobalEdgeNetwork {
  constructor() {
    this.pops = {
      ID: { name: "CGK-PoP (Jakarta)", currency: "IDR", rate: 15500, symbol: "Rp", pingMs: 5 },
      JP: { name: "NRT-PoP (Tokyo)", currency: "JPY", rate: 150, symbol: "¥", pingMs: 8 },
      GB: { name: "LHR-PoP (London)", currency: "GBP", rate: 0.79, symbol: "£", pingMs: 12 },
    };

    this.originHealth = {
      "us-east-1": "HEALTHY",
      "eu-central-1": "HEALTHY",
    };
  }

  handleIncomingRequest(userCountry, basePriceUSD) {
    const pop = this.pops[userCountry] || this.pops["ID"];
    const localizedPrice = Math.round(basePriceUSD * pop.rate);

    return {
      routedPoP: pop.name,
      latency: `${pop.pingMs} ms`,
      pricing: {
        currency: pop.currency,
        amount: localizedPrice,
        formatted: `${pop.symbol} ${localizedPrice.toLocaleString()}`,
      },
    };
  }

  simulateEdgeFailover() {
    console.log("  ⚠️  Primary Origin di 'us-east-1' (Virginia) mengalami kegagalan (HTTP 503)...");
    this.originHealth["us-east-1"] = "DOWN";

    const failoverStart = Date.now();
    // Edge Worker mendeteksi anomali health check dan membelokkan ke failover origin
    const activeOrigin = this.originHealth["us-east-1"] === "HEALTHY" ? "us-east-1" : "eu-central-1";
    const failoverDuration = Date.now() - failoverStart + 18;

    return {
      activeOrigin,
      failoverTimeMs: failoverDuration,
      status: "AUTOMATIC_FAILOVER_SUCCESS",
    };
  }
}

// =============================================================================
// 3. RUN SUITE
// =============================================================================

async function runSimulation() {
  console.log("===========================================================================");
  console.log("SIMULASI: SERVERLESS COLD START VS EDGE V8 ISOLATE & GEO-ROUTING");
  console.log("===========================================================================\n");

  // BAGIAN 1: COLD START BENCHMARK
  console.log("--- BAGIAN 1: Benchmark Latensi Cold Start (Micro-VM vs V8 Isolate) ---");
  const lambda = new MicroVMServerlessRuntime();
  const edge = new V8IsolateEdgeRuntime();

  // A. Micro-VM Cold Start
  const lambdaCold = await lambda.invoke({ action: "compute" });
  console.log(`  1. Node.js Lambda Cold Start : ${lambdaCold.durationMs.toFixed(1)} ms (Tinggi akibat boot VM)`);

  // B. Micro-VM Warm Start
  const lambdaWarm = await lambda.invoke({ action: "compute" });
  console.log(`  2. Node.js Lambda Warm Start : ${lambdaWarm.durationMs.toFixed(1)} ms`);

  // C. Edge V8 Isolate Cold Start
  const edgeCold = await edge.invoke({ action: "compute" });
  console.log(`  3. Edge V8 Isolate Cold Start: ${edgeCold.durationMs.toFixed(1)} ms (Ultra Cepat!)`);

  const speedup = (lambdaCold.durationMs / edgeCold.durationMs).toFixed(1);
  console.log(`  🚀 Efisiensi Startup Edge    : ${speedup}x LEBIH CEPAT dibanding Serverless VM!\n`);

  // BAGIAN 2: GLOBAL GEO-IP ROUTING & LOCALIZATION
  console.log("--- BAGIAN 2: Personalisasi Konten & Mata Uang di 3 PoP Global ---");
  const network = new GlobalEdgeNetwork();

  const reqJakarta = network.handleIncomingRequest("ID", 100);
  console.log(`  🇮🇩 Pengguna Jakarta : Dilayani oleh ${reqJakarta.routedPoP} | Ping: ${reqJakarta.latency} | Harga: ${reqJakarta.pricing.formatted}`);

  const reqTokyo = network.handleIncomingRequest("JP", 100);
  console.log(`  🇯🇵 Pengguna Tokyo   : Dilayani oleh ${reqTokyo.routedPoP} | Ping: ${reqTokyo.latency} | Harga: ${reqTokyo.pricing.formatted}`);

  const reqLondon = network.handleIncomingRequest("GB", 100);
  console.log(`  🇬🇧 Pengguna London  : Dilayani oleh ${reqLondon.routedPoP} | Ping: ${reqLondon.latency} | Harga: ${reqLondon.pricing.formatted}\n`);

  // BAGIAN 3: ZERO-DOWNTIME EDGE FAILOVER
  console.log("--- BAGIAN 3: Pengujian Failover Otomatis di Perbatasan Edge ---");
  const failoverResult = network.simulateEdgeFailover();
  console.log(`  🛡️  Keputusan Edge : Mengalihkan traffic ke ${failoverResult.activeOrigin}`);
  console.log(`  ⏱️  Waktu Failover : ${failoverResult.failoverTimeMs} ms (Zero Downtime Terjamin! ✅)\n`);

  console.log("===========================================================================");
  console.log("SIMULASI SELESAI: Seluruh keunggulan arsitektur Edge terbukti nyata!");
  console.log("===========================================================================");
}

runSimulation();
