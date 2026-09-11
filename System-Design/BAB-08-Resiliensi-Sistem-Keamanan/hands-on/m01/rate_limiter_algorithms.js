/**
 * LAB SIMULATION: Token Bucket vs Sliding Window Counter Rate Limiter
 * 
 * Tujuan:
 * 1. Menunjukkan implementasi O(1) Token Bucket dengan Lazy Refill.
 * 2. Menunjukkan kapabilitas toleransi burst pada Token Bucket.
 * 3. Menunjukkan Sliding Window Counter dengan estimasi akurat berbasis bobot waktu.
 */

// 1. TOKEN BUCKET (O(1) Memory & Lazy Refill Calculation)
class TokenBucketRateLimiter {
  constructor(capacity, refillRatePerSec) {
    this.capacity = capacity;
    this.refillRatePerSec = refillRatePerSec;
    this.tokens = capacity;
    this.lastRefillTime = Date.now();
  }

  // Refill kalkulasi dinamis (tidak perlu background interval)
  refill() {
    const now = Date.now();
    const elapsedSeconds = (now - this.lastRefillTime) / 1000;
    const tokensToAdd = elapsedSeconds * this.refillRatePerSec;

    this.tokens = Math.min(this.capacity, this.tokens + tokensToAdd);
    this.lastRefillTime = now;
  }

  allowRequest(tokensNeeded = 1) {
    this.refill();

    if (this.tokens >= tokensNeeded) {
      this.tokens -= tokensNeeded;
      return {
        allowed: true,
        remainingTokens: Math.floor(this.tokens),
        retryAfterSec: 0
      };
    } else {
      const tokensDeficit = tokensNeeded - this.tokens;
      const retryAfterSec = Math.ceil(tokensDeficit / this.refillRatePerSec);
      return {
        allowed: false,
        remainingTokens: Math.floor(this.tokens),
        retryAfterSec
      };
    }
  }
}

// 2. SLIDING WINDOW COUNTER (Approximation Memory-Efficient)
class SlidingWindowCounterLimiter {
  constructor(limitPerWindow, windowSizeMs = 1000) {
    this.limit = limitPerWindow;
    this.windowSizeMs = windowSizeMs;
    this.currentWindowKey = Math.floor(Date.now() / windowSizeMs);
    this.currentCount = 0;
    this.previousCount = 0;
  }

  allowRequest() {
    const now = Date.now();
    const windowKey = Math.floor(now / this.windowSizeMs);

    if (windowKey !== this.currentWindowKey) {
      // Geser window
      if (windowKey === this.currentWindowKey + 1) {
        this.previousCount = this.currentCount;
      } else {
        this.previousCount = 0; // Lebih dari 1 window terlewat
      }
      this.currentWindowKey = windowKey;
      this.currentCount = 0;
    }

    // Hitung bobot tumpang tindih waktu
    const timeIntoCurrentWindow = now % this.windowSizeMs;
    const currentWindowWeight = timeIntoCurrentWindow / this.windowSizeMs;
    const previousWindowWeight = 1 - currentWindowWeight;

    const estimatedCount = Math.floor((this.previousCount * previousWindowWeight) + this.currentCount);

    if (estimatedCount < this.limit) {
      this.currentCount += 1;
      return { allowed: true, estimatedCount: estimatedCount + 1, limit: this.limit };
    } else {
      return { allowed: false, estimatedCount, limit: this.limit };
    }
  }
}

// ======================= PENGUJIAN =======================
console.log("===================================================================");
console.log("🛠️  PENGUJIAN 1: TOKEN BUCKET DENGAN BURST TRAFFIC");
console.log("===================================================================");
// Kapasitas bucket = 5 token, refill = 2 token per detik
const bucket = new TokenBucketRateLimiter(5, 2);

console.log("-> Mengirim 7 request beruntun dalam 1 detik (Burst):");
for (let i = 1; i <= 7; i++) {
  const res = bucket.allowRequest(1);
  if (res.allowed) {
    console.log(`Req #${i}: ✅ 200 OK | Sisa Token: ${res.remainingTokens}`);
  } else {
    console.log(`Req #${i}: ❌ 429 Too Many Requests | Retry-After: ${res.retryAfterSec}s`);
  }
}

console.log("\n-> Menunggu 1.5 detik agar token terisi ulang secara lazy...");
setTimeout(() => {
  console.log("-> Mengirim 2 request baru setelah menunggu:");
  for (let i = 8; i <= 9; i++) {
    const res = bucket.allowRequest(1);
    if (res.allowed) {
      console.log(`Req #${i}: ✅ 200 OK | Sisa Token: ${res.remainingTokens}`);
    } else {
      console.log(`Req #${i}: ❌ 429 Too Many Requests | Retry-After: ${res.retryAfterSec}s`);
    }
  }

  console.log("\n===================================================================");
  console.log("🛠️  PENGUJIAN 2: SLIDING WINDOW COUNTER");
  console.log("===================================================================");
  const sliding = new SlidingWindowCounterLimiter(3, 1000); // Max 3 req per detik

  for (let i = 1; i <= 5; i++) {
    const res = sliding.allowRequest();
    console.log(`Sliding Req #${i}: ${res.allowed ? "✅ 200 OK" : "❌ 429 RATELIMIT"} (Est Count: ${res.estimatedCount}/${res.limit})`);
  }

  console.log("\n Kesimpulan:");
  console.log("1. Token Bucket mengizinkan burst traffic sesaat hingga batas kapasitas (5 req lolos).");
  console.log("2. Request ke-6 dan ke-7 ditolak dengan HTTP 429 dan kalkulasi Retry-After akurat.");
  console.log("3. Token terisi kembali secara dinamis (lazy) tanpa overhead thread/timer terpisah.");
}, 1500);
