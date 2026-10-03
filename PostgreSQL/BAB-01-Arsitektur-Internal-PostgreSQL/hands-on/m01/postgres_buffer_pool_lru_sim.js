/**
 * Hands-on M01: PostgreSQL Shared Buffer Pool & Clock-Sweep Replacement Simulator
 * Track: PostgreSQL Mastery - BAB 01
 * 
 * Demonstrasi mekanisme internal PostgreSQL:
 * 1. Fixed-size Buffer Pool Frames
 * 2. Clock-Sweep Replacement Algorithm (usage_count, pin/unpin)
 * 3. Buffer Table lookup (Hash table RelFileNode + BlockNumber -> Buffer ID)
 * 4. Cache Hit Ratio tracking
 * 5. Zero external dependencies (Node.js)
 */

const ANSI = {
  reset: "\x1b[0m",
  bold: "\x1b[1m",
  green: "\x1b[32m",
  cyan: "\x1b[36m",
  yellow: "\x1b[33m",
  red: "\x1b[31m",
  magenta: "\x1b[35m"
};

class BufferDesc {
  constructor(bufId) {
    this.bufId = bufId;
    this.tag = null; // Key: { relNode, blockNum }
    this.usageCount = 0;
    this.refCount = 0; // Pin count
    this.isDirty = false;
  }

  isFree() {
    return this.tag === null;
  }

  isPinned() {
    return this.refCount > 0;
  }
}

class PostgresBufferPool {
  constructor(poolSize = 4) {
    this.poolSize = poolSize;
    this.buffers = Array.from({ length: poolSize }, (_, i) => new BufferDesc(i));
    this.bufferTable = new Map(); // Tag string -> bufId
    this.clockHand = 0;
    this.stats = { hits: 0, misses: 0, evictions: 0 };
  }

  _tagKey(tag) {
    return `${tag.relNode}:${tag.blockNum}`;
  }

  // Clock-sweep buffer replacement algorithm
  _findVictimBuffer() {
    let sweeps = 0;
    while (sweeps < this.poolSize * 2) {
      const buf = this.buffers[this.clockHand];
      
      if (!buf.isPinned()) {
        if (buf.usageCount > 0) {
          buf.usageCount--;
        } else {
          // Victim found!
          const victimId = this.clockHand;
          this.clockHand = (this.clockHand + 1) % this.poolSize;
          return victimId;
        }
      }

      this.clockHand = (this.clockHand + 1) % this.poolSize;
      sweeps++;
    }
    throw new Error("Out of memory: All buffers in shared_buffers are currently pinned!");
  }

  readBlock(relNode, blockNum) {
    const tag = { relNode, blockNum };
    const key = this._tagKey(tag);

    // 1. Check if block is already cached (Cache Hit)
    if (this.bufferTable.has(key)) {
      this.stats.hits++;
      const bufId = this.bufferTable.get(key);
      const buf = this.buffers[bufId];
      if (buf.usageCount < 5) buf.usageCount++;
      console.log(`  ${ANSI.green}[CACHE HIT]${ANSI.reset} Tag [${key}] found at Buffer #${bufId} (usage_count: ${buf.usageCount})`);
      return buf;
    }

    // 2. Cache Miss - Need to read from disk into buffer pool
    this.stats.misses++;
    console.log(`  ${ANSI.yellow}[CACHE MISS]${ANSI.reset} Tag [${key}] reading from disk...`);

    // Find free buffer or evict via clock-sweep
    let targetBufId = this.buffers.findIndex(b => b.isFree());
    if (targetBufId === -1) {
      targetBufId = this._findVictimBuffer();
      const victim = this.buffers[targetBufId];
      console.log(`  ${ANSI.magenta}[CLOCK SWEEP EVICTION]${ANSI.reset} Evicting Buffer #${targetBufId} (Tag: ${this._tagKey(victim.tag)})`);
      this.bufferTable.delete(this._tagKey(victim.tag));
      this.stats.evictions++;
    }

    const buf = this.buffers[targetBufId];
    buf.tag = tag;
    buf.usageCount = 1;
    buf.refCount = 0;
    buf.isDirty = false;
    this.bufferTable.set(key, targetBufId);

    return buf;
  }

  printState() {
    console.log("\n--- Shared Buffers State ---");
    this.buffers.forEach(b => {
      const tagStr = b.tag ? `${b.tag.relNode}:${b.tag.blockNum}` : "EMPTY";
      console.log(`[Buf #${b.bufId}] Tag: ${tagStr.padEnd(8)} | Usage: ${b.usageCount} | Pinned: ${b.refCount} | Dirty: ${b.isDirty}`);
    });
    const total = this.stats.hits + this.stats.misses;
    const hitRatio = total > 0 ? ((this.stats.hits / total) * 100).toFixed(1) : 0;
    console.log(`Stats -> Hits: ${this.stats.hits}, Misses: ${this.stats.misses}, Evictions: ${this.stats.evictions}, Hit Ratio: ${hitRatio}%\n`);
  }
}

// ==========================================
// TEST SUITE & RUNNER
// ==========================================
function runLab() {
  console.log(`${ANSI.bold}${ANSI.cyan}======================================================${ANSI.reset}`);
  console.log(`${ANSI.bold}${ANSI.cyan}  LAB HANDS-ON: POSTGRESQL SHARED BUFFER POOL SIM     ${ANSI.reset}`);
  console.log(`${ANSI.bold}${ANSI.cyan}======================================================${ANSI.reset}`);

  const pool = new PostgresBufferPool(3); // Small pool of 3 buffers to demonstrate clock sweep

  console.log(`\n${ANSI.bold}[Step 1] Loading initial blocks into buffer pool...${ANSI.reset}`);
  pool.readBlock("users_tbl", 0);
  pool.readBlock("users_tbl", 1);
  pool.readBlock("orders_tbl", 0);
  pool.printState();

  console.log(`${ANSI.bold}[Step 2] Repeated reads on users_tbl:0 (Increment usage_count)...${ANSI.reset}`);
  pool.readBlock("users_tbl", 0);
  pool.readBlock("users_tbl", 0);
  pool.printState();

  console.log(`${ANSI.bold}[Step 3] Loading new block (products_tbl:0), triggering Clock-Sweep...${ANSI.reset}`);
  pool.readBlock("products_tbl", 0);
  pool.printState();

  if (pool.stats.hits === 2 && pool.stats.evictions === 1) {
    console.log(`${ANSI.green}${ANSI.bold}✓ SUCCESS: PostgreSQL Buffer Pool & Clock-Sweep simulated correctly!${ANSI.reset}`);
  } else {
    throw new Error("Assertion failed on buffer pool statistics");
  }
}

runLab();
