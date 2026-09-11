/**
 * LAB SIMULATION: Distributed Rate Limiter Service with Batch Reservation & Fail-Open
 * 
 * Fitur:
 * 1. Distributed Cache Store (Redis Mock) dengan Atomic Operations.
 * 2. Multi-Gateway Simulation (2 instance gateway melayani user yang sama).
 * 3. Batch Token Reservation (Mengurangi network round-trip).
 * 4. Fail-Open Architecture (Jika Redis down, jangan blokir user yang sah!).
 */

class CentralizedRedisClusterMock {
  constructor() {
    this.store = new Map(); // key -> { tokens, lastRefill }
    this.isOnline = true;
  }

  // Atomic Lua Script Simulation: Reserve Batch of Tokens
  atomicReserveTokens(key, batchSize, maxCapacity, refillRatePerSec) {
    if (!this.isOnline) {
      throw new Error("REDIS_CONNECTION_REFUSED: Cluster is down!");
    }

    const now = Date.now();
    let record = this.store.get(key);

    if (!record) {
      record = { tokens: maxCapacity, lastRefill: now };
    } else {
      // Lazy Refill
      const elapsedSec = (now - record.lastRefill) / 1000;
      record.tokens = Math.min(maxCapacity, record.tokens + (elapsedSec * refillRatePerSec));
      record.lastRefill = now;
    }

    const tokensToGrant = Math.min(batchSize, Math.floor(record.tokens));
    record.tokens -= tokensToGrant;
    this.store.set(key, record);

    return {
      granted: tokensToGrant,
      remainingGlobal: Math.floor(record.tokens)
    };
  }
}

// API GATEWAY NODE (Edge Instance)
class ApiGatewayInstance {
  constructor(gatewayId, redisCluster, options = {}) {
    this.gatewayId = gatewayId;
    this.redisCluster = redisCluster;
    this.batchSize = options.batchSize || 10;
    this.localTokenCache = new Map(); // userId -> localTokenCount
    this.maxCapacity = options.maxCapacity || 50;
    this.refillRate = options.refillRate || 10;
  }

  handleRequest(userId) {
    let localTokens = this.localTokenCache.get(userId) || 0;

    // 1. Cek token di RAM Lokal Gateway (Latensi 0.01ms!)
    if (localTokens > 0) {
      this.localTokenCache.set(userId, localTokens - 1);
      return {
        allowed: true,
        source: "LOCAL_RAM_CACHE",
        localRemaining: localTokens - 1,
        gateway: this.gatewayId
      };
    }

    // 2. Token lokal habis -> Ambil Batch baru dari Redis Cluster
    try {
      const reservation = this.redisCluster.atomicReserveTokens(
        `ratelimit:${userId}`,
        this.batchSize,
        this.maxCapacity,
        this.refillRate
      );

      if (reservation.granted > 0) {
        // Simpan sisa batch ke lokal RAM (kurangi 1 untuk request saat ini)
        this.localTokenCache.set(userId, reservation.granted - 1);
        return {
          allowed: true,
          source: "CENTRAL_REDIS_BATCH_SYNC",
          batchAcquired: reservation.granted,
          localRemaining: reservation.granted - 1,
          globalRemaining: reservation.remainingGlobal,
          gateway: this.gatewayId
        };
      } else {
        return {
          allowed: false,
          source: "CENTRAL_REDIS_EMPTY",
          reason: "HTTP 429 Too Many Requests (Global Quota Exceeded)",
          gateway: this.gatewayId
        };
      }
    } catch (err) {
      // 3. FAIL-OPEN RESILIENCE STRATEGY
      console.warn(`⚠️ [${this.gatewayId}] Redis error: ${err.message}. Mengaktifkan mode FAIL-OPEN!`);
      return {
        allowed: true,
        source: "FAIL_OPEN_EMERGENCY_ALLOW",
        reason: "Request diizinkan demi availability saat redis down",
        gateway: this.gatewayId
      };
    }
  }
}

// ======================= PENGUJIAN SKENARIO =======================
const redis = new CentralizedRedisClusterMock();
const gatewayA = new ApiGatewayInstance("Gateway-US-East", redis, { batchSize: 5, maxCapacity: 15, refillRate: 5 });
const gatewayB = new ApiGatewayInstance("Gateway-US-West", redis, { batchSize: 5, maxCapacity: 15, refillRate: 5 });

console.log("===================================================================");
console.log("🛠️  PENGUJIAN 1: BATCH RESERVATION LINTAS DUA GATEWAY INSTANCE");
console.log("===================================================================\n");

const targetUser = "user_corp_alpha";

console.log("-> Request 1 masuk ke Gateway-US-East (Belum ada token lokal):");
console.log(gatewayA.handleRequest(targetUser));

console.log("\n-> Request 2 masuk ke Gateway-US-East (Hit Local Cache RAM! Super Cepat):");
console.log(gatewayA.handleRequest(targetUser));

console.log("\n-> Request 3 masuk ke Gateway-US-West (Meminjam batch independen dari Redis):");
console.log(gatewayB.handleRequest(targetUser));

console.log("\n===================================================================");
console.log("🛠️  PENGUJIAN 2: FAIL-OPEN RESILIENCE SAAT REDIS DOWN");
console.log("===================================================================\n");

// Habiskan token lokal gateway B
gatewayB.localTokenCache.set(targetUser, 0);

// Simulasikan Redis Down / Network Partition
console.log("💥 SIMULASI: Kluster Redis terputus (Network Partition / Crash)...");
redis.isOnline = false;

console.log("\n-> Request masuk ke Gateway-US-West saat Redis mati:");
const failOpenResult = gatewayB.handleRequest(targetUser);
console.log(failOpenResult);

console.log("\n Kesimpulan:");
console.log("1. Batch reservation memotong 80-90% traffic round-trip jaringan ke Redis.");
console.log("2. Dua gateway berbeda dapat berbagi kuota global yang sama secara konsisten.");
console.log("3. Kebijakan Fail-Open memastikan layanan bisnis tidak lumpuh saat cluster cache mengalami gangguan.");
