// binary-tick-processor.mjs
import { Buffer } from 'node:buffer';

/**
 * SKEMA DATA TICKER (Total: 24 Bytes per Transaksi)
 * Offset 0  - [Uint32] Transaction ID (4 byte)
 * Offset 4  - [Uint32] Timestamp Epoch Sec (4 byte)
 * Offset 8  - [Uint8Array(8)] Symbol (ASCII, 8 byte)
 * Offset 16 - [Float64] Price (8 byte)
 */
export const TICK_SIZE = 24;

export class BinaryMemoryPool {
  #buffer;
  #dataView;
  #capacity;
  #currentSlot = 0;

  constructor(maxTicks) {
    this.#capacity = maxTicks;
    // Alokasi memori berukuran masif di awal secara berkelanjutan (Contiguous Memory)
    this.#buffer = new ArrayBuffer(this.#capacity * TICK_SIZE);
    this.#dataView = new DataView(this.#buffer);
    this.symbolDecoder = new TextDecoder('ascii');
  }

  get capacity() {
    return this.#capacity;
  }

  get currentUsage() {
    return this.#currentSlot;
  }

  /**
   * Menulis langsung ke memory heap tanpa membuat objek JS intermediet.
   */
  writeTick(txId, timestamp, symbolStr, price) {
    if (this.#currentSlot >= this.#capacity) {
      throw new Error("Pool Buffer Penuh! Wajib flush sebelum alokasi baru.");
    }

    const baseOffset = this.#currentSlot * TICK_SIZE;

    // Tulis Tx ID
    this.#dataView.setUint32(baseOffset + 0, txId, true);
    // Tulis Timestamp
    this.#dataView.setUint32(baseOffset + 4, timestamp, true);

    // Tulis Simbol (ASCII max 8 karakter)
    for (let i = 0; i < 8; i++) {
      const charCode = i < symbolStr.length ? symbolStr.charCodeAt(i) : 0;
      this.#dataView.setUint8(baseOffset + 8 + i, charCode);
    }

    // Tulis Price
    this.#dataView.setFloat64(baseOffset + 16, price, true);

    this.#currentSlot++;
    return baseOffset;
  }

  /**
   * Pembacaan data in-place langsung dari offset, menghindari GC Object Creation.
   */
  readPrice(slotIndex) {
    const baseOffset = slotIndex * TICK_SIZE;
    return this.#dataView.getFloat64(baseOffset + 16, true);
  }

  readTxId(slotIndex) {
    const baseOffset = slotIndex * TICK_SIZE;
    return this.#dataView.getUint32(baseOffset + 0, true);
  }

  /**
   * Daur ulang memori instan tanpa intervensi GC (O(1) operation).
   */
  reset() {
    this.#currentSlot = 0;
  }

  getRawBuffer() {
    return this.#buffer;
  }
}

// =========================================================================
// SIMULASI LOAD HIGH-THROUGHPUT
// =========================================================================

const BATCH_SIZE = 1_000_000;
const memoryPool = new BinaryMemoryPool(BATCH_SIZE);

console.time("Proses 1 Juta Tick (Zero-Allocation Pool)");

for (let i = 0; i < BATCH_SIZE; i++) {
  memoryPool.writeTick(i, 1710000000 + i, "BBCA", 9850.50 + (i % 100));
}

// Kalkulasi agregasi in-place
let totalValue = 0;
for (let i = 0; i < BATCH_SIZE; i++) {
  totalValue += memoryPool.readPrice(i);
}

console.timeEnd("Proses 1 Juta Tick (Zero-Allocation Pool)");
console.log(`Total Volume Dihitung: ${totalValue.toFixed(2)}`);
console.log(`Memori fisik statis dialokasikan: ${(BATCH_SIZE * TICK_SIZE) / (1024 * 1024)} MB`);

// Reset untuk reuse tanpa memicu Garbage Collector
memoryPool.reset();
