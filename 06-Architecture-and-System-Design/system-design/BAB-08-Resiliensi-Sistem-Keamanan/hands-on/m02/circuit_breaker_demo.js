/**
 * LAB SIMULATION: Circuit Breaker State Transitions & Fail-Fast Fallback
 * 
 * FSM States:
 * 1. CLOSED: Normal, memanggil downstream.
 * 2. OPEN: Downstream error melebihi threshold -> Langsung fail-fast ke Fallback tanpa panggil remote!
 * 3. HALF-OPEN: Cooldown habis -> Kirim 1 trial probe -> Jika sukses, kembali CLOSED.
 */

const STATE = {
  CLOSED: "CLOSED (Normal)",
  OPEN: "OPEN (Trip / Broken - Fail Fast)",
  HALF_OPEN: "HALF-OPEN (Trial Probe)"
};

class CircuitBreaker {
  constructor(options = {}) {
    this.failureThreshold = options.failureThreshold || 3; // 3 kali gagal berturut-turut -> OPEN
    this.cooldownTimeoutMs = options.cooldownTimeoutMs || 1000; // Tunggu 1s sebelum HALF-OPEN
    this.state = STATE.CLOSED;
    this.failureCount = 0;
    this.lastFailureTime = null;
  }

  async execute(actionFn, fallbackFn) {
    const now = Date.now();

    // 1. Evaluasi transisi dari OPEN ke HALF-OPEN
    if (this.state === STATE.OPEN) {
      if (now - this.lastFailureTime >= this.cooldownTimeoutMs) {
        console.log(`\n⏳ [CircuitBreaker] Cooldown ${this.cooldownTimeoutMs}ms selesai. Transisi: OPEN -> HALF-OPEN`);
        this.state = STATE.HALF_OPEN;
      } else {
        // Masih dalam masa OPEN -> Fail Fast!
        console.log(`⚡ [CircuitBreaker] State masih OPEN! Fail-Fast aktif -> Menjalankan Fallback.`);
        return fallbackFn();
      }
    }

    // 2. Eksekusi panggilan nyata (CLOSED atau HALF-OPEN)
    try {
      console.log(`🌐 [CircuitBreaker] Mengirim request ke downstream service (State: ${this.state})...`);
      const result = await actionFn();
      this.onSuccess();
      return result;
    } catch (err) {
      this.onFailure(err);
      return fallbackFn();
    }
  }

  onSuccess() {
    if (this.state === STATE.HALF_OPEN) {
      console.log(`🎉 [CircuitBreaker] Trial probe sukses! Transisi: HALF-OPEN -> CLOSED (Downstream Sehat)`);
    }
    this.state = STATE.CLOSED;
    this.failureCount = 0;
  }

  onFailure(err) {
    this.failureCount += 1;
    this.lastFailureTime = Date.now();
    console.log(`⚠️  [CircuitBreaker] Panggilan gagal (${this.failureCount}/${this.failureThreshold}): ${err.message}`);

    if (this.state === STATE.HALF_OPEN || this.failureCount >= this.failureThreshold) {
      console.log(`🚨 [CircuitBreaker] Threshold tercapai! Transisi -> OPEN (Memutus Aliran Trafik)`);
      this.state = STATE.OPEN;
    }
  }
}

// SIMULASI DOWNSTREAM SERVICE
let isDownstreamHealthy = true;

const downstreamCall = () => {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      if (isDownstreamHealthy) {
        resolve({ statusCode: 200, data: "Data Rekomendasi Produk Terkini (AI Personal)" });
      } else {
        reject(new Error("503 Service Unavailable / Connection Timeout (3000ms)"));
      }
    }, 50);
  });
};

const fallbackCall = () => {
  return { statusCode: 200, isFallback: true, data: "Data Default: 5 Produk Terlaris (Local Cache)" };
};

// ======================= PENGUJIAN ALUR =======================
async function runLab() {
  console.log("===================================================================");
  console.log("🛠️  SIMULASI RESILIENSI SISTEM: CIRCUIT BREAKER FSM");
  console.log("===================================================================\n");

  const cb = new CircuitBreaker({ failureThreshold: 3, cooldownTimeoutMs: 800 });

  // 1. Fase Normal (CLOSED)
  console.log("--- FASE 1: Layanan Downstream Normal (State: CLOSED) ---");
  const res1 = await cb.execute(downstreamCall, fallbackCall);
  console.log(`Response: [${res1.statusCode}] ${res1.data}\n`);

  // 2. Downstream Tumbang
  console.log("--- FASE 2: Downstream Tiba-tiba Tumbang (Memicu Trip ke OPEN) ---");
  isDownstreamHealthy = false;
  await cb.execute(downstreamCall, fallbackCall);
  await cb.execute(downstreamCall, fallbackCall);
  await cb.execute(downstreamCall, fallbackCall); // Ke-3 -> Trip ke OPEN!

  // 3. Fase Fail-Fast (OPEN)
  console.log("\n--- FASE 3: Trafik Datang Saat State OPEN (Fail-Fast Tanpa Menunggu Timeout) ---");
  const startFailFast = Date.now();
  const resFast = await cb.execute(downstreamCall, fallbackCall);
  const elapsed = Date.now() - startFailFast;
  console.log(`Response Cepat (${elapsed}ms): [${resFast.statusCode}] ${resFast.data} (Fallback: ${resFast.isFallback})`);

  // 4. Fase Cooldown & Pemulihan (HALF-OPEN -> CLOSED)
  console.log("\n--- FASE 4: Menunggu Cooldown 900ms & Pemulihan Layanan ---");
  await new Promise(r => setTimeout(r, 900));
  isDownstreamHealthy = true; // Downstream sudah diperbaiki oleh tim ops

  console.log("-> Mengirim request saat cooldown habis (Uji Coba Trial Probe):");
  const resRecovered = await cb.execute(downstreamCall, fallbackCall);
  console.log(`Response Akhir: [${resRecovered.statusCode}] ${resRecovered.data}`);
  console.log(`Status Akhir Circuit Breaker: ${cb.state}`);

  console.log("\n Kesimpulan:");
  console.log("1. Saat downstream down, Circuit Breaker langsung memutus koneksi (OPEN).");
  console.log("2. Request berikutnya dilayani seketika (<1ms) via Fallback tanpa menunggu socket timeout.");
  console.log("3. Circuit Breaker pulih secara aman melalui uji coba probe (HALF-OPEN) saat downstream sembuh.");
}

runLab();
