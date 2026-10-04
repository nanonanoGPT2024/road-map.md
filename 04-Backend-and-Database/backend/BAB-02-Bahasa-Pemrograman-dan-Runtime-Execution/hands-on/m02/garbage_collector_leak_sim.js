/**
 * Mark-and-Sweep Garbage Collector & JIT Hot-Spot Simulator
 * 
 * Mensimulasikan mekanisme runtime internal:
 * 1. Mark-and-Sweep Tracing GC: Penelusuran graf objek dari GC Roots.
 * 2. Deteksi Memory Leak: Objek yang tersangkut di variabel global (Unbounded Cache).
 * 3. JIT Hot-Spot Compilation: Transisi dari Interpreter lambat ke Native Machine Code,
 *    dan simulasi JIT Bailout (Deoptimization) saat terjadi Type Inconsistency.
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

function log(module, msg, color = ANSI.reset) {
  console.log(`${color}[${module}] ${msg}${ANSI.reset}`);
}

// ================= 1. MARK-AND-SWEEP GC SIMULATOR =================
class GarbageCollectorSimulator {
  constructor() {
    this.heap = new Map(); // id -> { id, sizeKB, refs: [id], isMarked: false }
    this.gcRoots = new Set(); // ID objek yang menjadi GC Roots (global / stack)
  }

  allocate(id, sizeKB, refs = []) {
    const obj = { id, sizeKB, refs, isMarked: false };
    this.heap.set(id, obj);
    log("heap-allocator", `Allocated '${id}' (${sizeKB} KB)`, ANSI.cyan);
    return id;
  }

  addRoot(id) {
    this.gcRoots.add(id);
    log("gc-engine", `Menandai '${id}' sebagai GC ROOT (Akses global/stack aktif)`, ANSI.yellow);
  }

  removeRoot(id) {
    this.gcRoots.delete(id);
    log("gc-engine", `Melepaskan '${id}' dari GC ROOT`, ANSI.yellow);
  }

  collect() {
    log("gc-engine", `=== MEMULAI SIKLUS TRACING GARBAGE COLLECTION ===`, ANSI.bold);

    // 1. Fase Mark: Mulai dari GC Roots
    log("gc-phase", `Fase 1: MARKING... Menelusuri seluruh pointer dari GC Roots [${Array.from(this.gcRoots).join(", ")}]`, ANSI.magenta);
    for (const rootId of this.gcRoots) {
      this._markObject(rootId);
    }

    // 2. Fase Sweep: Hapus semua yang tidak tertandai
    log("gc-phase", `Fase 2: SWEEPING... Memindai seluruh memori heap dan membebaskan sampah`, ANSI.magenta);
    let freedBytes = 0;
    let freedCount = 0;

    for (const [id, obj] of this.heap.entries()) {
      if (!obj.isMarked) {
        log("gc-sweep", `-> RECLAIMING: Objek '${id}' tidak terjangkau (Unreachable)! Memori ${obj.sizeKB} KB dibebaskan.`, ANSI.green);
        freedBytes += obj.sizeKB;
        freedCount++;
        this.heap.delete(id);
      } else {
        // Reset penanda untuk siklus GC berikutnya
        obj.isMarked = false;
      }
    }

    log("gc-engine", `Hasil GC: ${freedCount} objek dibersihkan, ${freedBytes} KB memori dikembalikan ke sistem.`, ANSI.bold + ANSI.green);
    log("gc-engine", `Sisa Objek di Heap: ${this.heap.size} objek aktif.`, ANSI.cyan);
  }

  _markObject(id) {
    const obj = this.heap.get(id);
    if (!obj || obj.isMarked) return;

    obj.isMarked = true;
    log("gc-mark", `-> Marked ALIVE: '${id}' (${obj.sizeKB} KB)`, ANSI.yellow);

    for (const refId of obj.refs) {
      this._markObject(refId);
    }
  }
}

// ================= 2. JIT COMPILER & DEOPTIMIZATION SIMULATOR =================
class JITCompilerSimulator {
  constructor(functionName) {
    this.name = functionName;
    this.callCount = 0;
    this.isCompiled = false;
    this.expectedType = null;
  }

  invoke(arg1, arg2) {
    this.callCount++;
    const currentType = typeof arg1;

    // Tahap 1: Fast Interpreter (Dingin)
    if (!this.isCompiled) {
      if (this.callCount < 5) {
        log("interpreter", `[Call #${this.callCount}] Mengeksekusi '${this.name}' via Bytecode Interpreter (Kecepatan: Normal)`, ANSI.cyan);
      }

      // Deteksi Hot Spot: Jika fungsi dipanggil 5 kali (skala simulasi)
      if (this.callCount === 5) {
        log("jit-profiler", `HOT SPOT DETECTED! Fungsi '${this.name}' dipanggil berkali-kali!`, ANSI.yellow);
        log("jit-turbofan", `JIT mengompilasi '${this.name}' langsung ke Native Machine Code Assembly x86_64!`, ANSI.magenta);
        log("jit-turbofan", `Inline Caching: Mengasumsikan tipe data input selalu '${currentType}' (Monomorphic)`, ANSI.magenta);
        this.isCompiled = true;
        this.expectedType = currentType;
      }
      return arg1 + arg2;
    }

    // Tahap 2: Native Machine Code Execution (Super Cepat)
    if (currentType === this.expectedType) {
      log("jit-native", `[Call #${this.callCount}] Eksekusi NATIVE ASSEMBLY x86_64 (Instruksi ADD EAX, EBX) -> Kecepatan 20x Lebih Cepat!`, ANSI.green);
      return arg1 + arg2;
    }

    // Tahap 3: DEOPTIMIZATION (BAILOUT!)
    log("jit-bailout", `PERINGATAN DEOPTIMIZATION! Tipe berubah: Diharapkan '${this.expectedType}', diterima '${currentType}'!`, ANSI.red);
    log("jit-bailout", `Asumsi JIT gagal! Membuang native code assembly dan beralih kembali ke Interpreter lambat!`, ANSI.red);
    this.isCompiled = false;
    return arg1 + arg2;
  }
}

// ================= SIMULASI EKSEKUSI =================
console.log(`${ANSI.bold}================================================================${ANSI.reset}`);
console.log(`${ANSI.bold}      GARBAGE COLLECTION & JIT COMPILATION SIMULATOR ENGINE     ${ANSI.reset}`);
console.log(`${ANSI.bold}================================================================${ANSI.reset}\n`);

// 1. Demonstrasi Garbage Collector & Memory Leak
console.log(`--- [BAGIAN 1: SIKLUS MARK-AND-SWEEP & MEMORY LEAK] ---`);
const gc = new GarbageCollectorSimulator();

// Alokasi Objek Ephemeral (Normal)
gc.allocate("local-var-req-1", 128);
gc.allocate("local-var-req-2", 256);

// Alokasi Objek yang terikat ke Global Root (Memory Leak)
const cacheId = gc.allocate("global-cache-array", 512, ["leaked-token-data"]);
gc.allocate("leaked-token-data", 1024);
gc.addRoot(cacheId); // Global Root menahan 'global-cache-array'

console.log("\n-> Menjalankan Siklus GC Pertama:");
gc.collect();

console.log("\n-> Simulasi Perbaikan Memory Leak: Menghapus Global Root Cache:");
gc.removeRoot(cacheId);
gc.collect();

// 2. Demonstrasi JIT Compiler & Bailout
console.log(`\n--- [BAGIAN 2: JIT HOT SPOT COMPILATION & DEOPTIMIZATION] ---`);
const jit = new JITCompilerSimulator("addNumbers");

for (let i = 1; i <= 6; i++) {
  jit.invoke(10, 20);
}

console.log("\n-> Menguji Ketahanan JIT dengan Input Tipe Tidak Konsisten (String):");
jit.invoke("Halo ", "Dunia");

console.log(`\n${ANSI.bold}Seluruh mekanisme Garbage Collection dan JIT Optimization tervalidasi!${ANSI.reset}`);
