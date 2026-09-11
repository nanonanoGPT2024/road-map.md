/**
 * LAB TOOL: Automated System Design Capacity & Resource Planner
 * 
 * Tool CLI untuk menghitung estimasi Back-of-the-Envelope secara presisi:
 * - Throughput QPS (Average & Peak)
 * - Storage Growth 5 Tahun (Raw, Indexes, 3x Replication)
 * - Bandwidth Ingress / Egress (Gbps)
 * - Caching RAM (Pareto 80/20)
 * - Estimasi Jumlah Server Web Pods
 */

class CapacityPlanner {
  constructor(config) {
    this.name = config.name;
    this.dau = config.dau; // Daily Active Users
    this.writesPerUserPerDay = config.writesPerUserPerDay;
    this.readsPerUserPerDay = config.readsPerUserPerDay;
    this.avgPayloadWriteBytes = config.avgPayloadWriteBytes;
    this.avgPayloadReadBytes = config.avgPayloadReadBytes;
    this.peakMultiplier = config.peakMultiplier || 2.5; // Jam sibuk
    this.replicationFactor = config.replicationFactor || 3; // Master + 2 Replicas
    this.indexOverheadRatio = config.indexOverheadRatio || 1.4; // 40% tambahan untuk B-Tree index
    this.singleServerQpsCapacity = config.singleServerQpsCapacity || 1500; // 1 pod 8 vCPU
  }

  calculate() {
    const SECONDS_PER_DAY = 86400;

    // 1. Throughput Calculations
    const totalWritesPerDay = this.dau * this.writesPerUserPerDay;
    const totalReadsPerDay = this.dau * this.readsPerUserPerDay;

    const avgWriteQps = Math.round(totalWritesPerDay / SECONDS_PER_DAY);
    const peakWriteQps = Math.round(avgWriteQps * this.peakMultiplier);

    const avgReadQps = Math.round(totalReadsPerDay / SECONDS_PER_DAY);
    const peakReadQps = Math.round(avgReadQps * this.peakMultiplier);

    // 2. Storage Calculations
    const dailyRawStorageBytes = totalWritesPerDay * this.avgPayloadWriteBytes;
    const yearlyRawStorageBytes = dailyRawStorageBytes * 365;
    const fiveYearRawBytes = yearlyRawStorageBytes * 5;

    // Storage Riil (Index + Replikasi)
    const fiveYearRealBytes = fiveYearRawBytes * this.indexOverheadRatio * this.replicationFactor;

    // 3. Bandwidth Calculations (Bits per second)
    const ingressBps = (dailyRawStorageBytes * 8) / SECONDS_PER_DAY;
    const ingressGbps = (ingressBps / 1e9).toFixed(3);

    const dailyReadBytes = totalReadsPerDay * this.avgPayloadReadBytes;
    const egressBps = (dailyReadBytes * 8) / SECONDS_PER_DAY;
    const egressGbps = (egressBps / 1e9).toFixed(3);

    // 4. Cache Memory Sizing (Pareto 80/20: Cache 20% of daily read data)
    const cacheBytes = dailyReadBytes * 0.20;
    const cacheGb = (cacheBytes / (1024 ** 3)).toFixed(2);

    // 5. Server Count
    const totalPeakQps = peakWriteQps + peakReadQps;
    const baseServersNeeded = Math.ceil(totalPeakQps / this.singleServerQpsCapacity);
    const resilientServersNeeded = Math.ceil(baseServersNeeded * 1.3); // Buffer redundansi 30%

    return {
      name: this.name,
      throughput: {
        avgWriteQps,
        peakWriteQps,
        avgReadQps,
        peakReadQps,
        totalPeakQps,
        readToWriteRatio: `${Math.round(avgReadQps / avgWriteQps)}:1`
      },
      storage: {
        dailyRawGB: (dailyRawStorageBytes / (1024 ** 3)).toFixed(2),
        fiveYearRawTB: (fiveYearRawBytes / (1024 ** 4)).toFixed(2),
        fiveYearRealTotalTB: (fiveYearRealBytes / (1024 ** 4)).toFixed(2)
      },
      network: {
        ingressGbps,
        egressGbps
      },
      cache: {
        pareto20PercentDailyRAM_GB: cacheGb
      },
      infrastructure: {
        recommendedWebPods: resilientServersNeeded
      }
    };
  }
}

// Skenario Studi Kasus: Twitter / X Scaled System
const twitterSpec = new CapacityPlanner({
  name: "Twitter / X System Architecture",
  dau: 250_000_000, // 250 Juta DAU
  writesPerUserPerDay: 2, // 2 Tweets / hari
  readsPerUserPerDay: 25, // 25 Timeline refreshes / hari
  avgPayloadWriteBytes: 500, // 500 bytes per tweet (teks + metadata)
  avgPayloadReadBytes: 10_000, // 10 KB per timeline load (20 tweets ringkas)
  peakMultiplier: 2.5,
  singleServerQpsCapacity: 1200
});

console.log("===================================================================");
console.log("📊 HASIL PERHITUNGAN CAPACITY PLANNING & RESOURCE ESTIMATION");
console.log("===================================================================\n");
const results = twitterSpec.calculate();

console.log(`📌 Sistem: ${results.name}`);
console.log(`-------------------------------------------------------------------`);
console.log(`⚡ Throughput:`);
console.log(`   - Write QPS: Rata-rata = ${results.throughput.avgWriteQps.toLocaleString()} | Peak = ${results.throughput.peakWriteQps.toLocaleString()}`);
console.log(`   - Read QPS : Rata-rata = ${results.throughput.avgReadQps.toLocaleString()} | Peak = ${results.throughput.peakReadQps.toLocaleString()}`);
console.log(`   - Rasio Read/Write: ${results.throughput.readToWriteRatio}`);
console.log(`   - Total Peak QPS  : ${results.throughput.totalPeakQps.toLocaleString()} QPS\n`);

console.log(`💾 Penyimpanan Data (Storage):`);
console.log(`   - Data Mentah Harian : ${results.storage.dailyRawGB} GB / hari`);
console.log(`   - Data Mentah 5 Tahun: ${results.storage.fiveYearRawTB} TB`);
console.log(`   - Kebutuhan Riil 5 Thn: ${results.storage.fiveYearRealTotalTB} TB (Termasuk Index & 3x Replikasi)\n`);

console.log(`🌐 Bandwidth Jaringan:`);
console.log(`   - Ingress (Masuk)  : ${results.network.ingressGbps} Gbps`);
console.log(`   - Egress (Keluar)  : ${results.network.egressGbps} Gbps (Tinggi! Wajib CDN)\n`);

console.log(`🧠 Cache Memory (Pareto 80/20):`);
console.log(`   - Kebutuhan RAM Redis Harian: ${results.cache.pareto20PercentDailyRAM_GB} GB RAM\n`);

console.log(`🖥️ Rekomendasi Infrastruktur:`);
console.log(`   - Estimasi Web Pods/Servers : ${results.infrastructure.recommendedWebPods} Pods (Kapasitas Peak + 30% Buffer)`);
console.log(`===================================================================`);
