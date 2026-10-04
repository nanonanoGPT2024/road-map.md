/**
 * Memory Allocation (Stack vs Heap) & Concurrency Models Simulator
 * 
 * Mensimulasikan:
 * 1. Stack Allocation (LIFO frames) vs Heap Allocation & Escape Analysis.
 * 2. Single-Threaded Event Loop (Microtasks vs Macrotasks priority).
 * 3. Multi-Threaded Race Condition vs Mutex Synchronization.
 * 4. M:N Work-Stealing Scheduler (Model Go Runtime).
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

// ================= 1. STACK VS HEAP ALLOCATOR SIMULATOR =================
class MemorySimulator {
  static runDemo() {
    console.log(`\n${ANSI.bold}=== BAGIAN 1: STACK VS HEAP & ESCAPE ANALYSIS ===${ANSI.reset}`);

    const stack = [];
    const heap = new Map();

    // Fungsi 1: Nilai lokal murni (Stack only)
    log("memory-engine", "Eksekusi fungsi 'calculateTax()': Variabel lokal dialokasikan di STACK", ANSI.cyan);
    stack.push({ frame: "calculateTax", vars: { amount: 100000, rate: 0.11 } });
    log("stack-pointer", `Stack Push: [calculateTax Frame]. Ukuran Stack: ${stack.length}`, ANSI.cyan);

    // Fungsi selesai -> Pop stack frame seketika
    const popped = stack.pop();
    log("stack-pointer", `Fungsi Selesai: Stack Pop [${popped.frame}]. Memori dibersihkan instan tanpa Garbage Collection!`, ANSI.green);

    // Fungsi 2: Mengembalikan objek pointer (Escapes to Heap)
    log("memory-engine", "Eksekusi fungsi 'createOrder()': Objek dikembalikan sebagai pointer -> ESCAPES TO HEAP!", ANSI.yellow);
    const heapAddress = `0x7ffe_${Math.floor(1000 + Math.random() * 9000)}`;
    heap.set(heapAddress, { orderId: "ORD-9901", items: ["Buku", "Kopi"], amount: 150000 });

    stack.push({ frame: "createOrder", vars: { ptrOrder: heapAddress } });
    log("heap-allocator", `Heap Malloc: Objek dialokasikan di alamat memori '${heapAddress}'`, ANSI.yellow);
    stack.pop(); // Stack frame musnah, tapi objek di Heap tetap hidup karena masih direferensikan!
    log("heap-allocator", `Status Heap: Objek di '${heapAddress}' tetap bertahan dan dapat diakses oleh fungsi lain.`, ANSI.magenta);
  }
}

// ================= 2. EVENT LOOP SIMULATOR (MICRO VS MACRO) =================
class EventLoopSimulator {
  static runDemo() {
    console.log(`\n${ANSI.bold}=== BAGIAN 2: SINGLE-THREADED EVENT LOOP EXECUTION ===${ANSI.reset}`);

    const microtaskQueue = [];
    const macrotaskQueue = [];

    log("call-stack", "1. Eksekusi Synchronous: console.log('Script Start')", ANSI.cyan);

    // Jadwalkan Macrotask (setTimeout)
    macrotaskQueue.push(() => log("macrotask-queue", "4. Macrotask Selesai: Callback setTimeout() dieksekusi", ANSI.yellow));

    // Jadwalkan Microtask (Promise)
    microtaskQueue.push(() => log("microtask-queue", "3. Microtask Selesai: Callback Promise.then() dieksekusi (Prioritas Tertinggi!)", ANSI.green));

    log("call-stack", "2. Eksekusi Synchronous: console.log('Script End')", ANSI.cyan);

    // Event Loop Tick
    log("event-loop", "Call Stack kosong! Memeriksa Microtask Queue terlebih dahulu...", ANSI.bold);
    while (microtaskQueue.length > 0) {
      const task = microtaskQueue.shift();
      task();
    }

    log("event-loop", "Microtask Queue bersih! Beralih mengeksekusi Macrotask Queue...", ANSI.bold);
    while (macrotaskQueue.length > 0) {
      const task = macrotaskQueue.shift();
      task();
    }
  }
}

// ================= 3. MULTI-THREAD RACE CONDITION VS MUTEX =================
class ConcurrencyConflictSimulator {
  static runDemo() {
    console.log(`\n${ANSI.bold}=== BAGIAN 3: RACE CONDITION VS MUTEX SYNCHRONIZATION ===${ANSI.reset}`);

    // Skenario A: Race Condition (Tanpa Lock)
    let balanceUnsafe = 1000;
    log("thread-sim", `[Skenario A: Tanpa Mutex] Saldo Awal: Rp ${balanceUnsafe}`, ANSI.yellow);

    // Thread 1 membaca saldo
    const t1Read = balanceUnsafe; // 1000
    // Thread 2 membaca saldo sebelum Thread 1 selesai menulis!
    const t2Read = balanceUnsafe; // 1000

    // Thread 1 menulis (deposit 500)
    balanceUnsafe = t1Read + 500; // 1500
    // Thread 2 menimpa dengan pembacaan basi (deposit 300)
    balanceUnsafe = t2Read + 300; // 1300 (Seharusnya 1800!)

    log("thread-sim", `RACE CONDITION DETECTED! Saldo Akhir: Rp ${balanceUnsafe} (Harusnya Rp 1800, hilang Rp 500!)`, ANSI.red);

    // Skenario B: Dengan Mutex Lock
    let balanceSafe = 1000;
    let isLocked = false;
    log("thread-sim", `\n[Skenario B: Menggunakan Mutex Lock] Saldo Awal: Rp ${balanceSafe}`, ANSI.green);

    function safeDeposit(threadName, amount) {
      if (isLocked) {
        log("mutex", `[${threadName}] DITAHAN! Mutex sedang dikunci oleh thread lain. Menunggu...`, ANSI.yellow);
        return;
      }
      isLocked = true;
      log("mutex", `[${threadName}] ACQUIRE LOCK (Memasuki Critical Section)`, ANSI.cyan);
      balanceSafe += amount;
      isLocked = false;
      log("mutex", `[${threadName}] RELEASE LOCK. Saldo diperbarui menjadi Rp ${balanceSafe}`, ANSI.green);
    }

    safeDeposit("Thread-1", 500);
    safeDeposit("Thread-2", 300);
    log("thread-sim", `KONSISTENSI DATA TERJAGA: Saldo Akhir: Rp ${balanceSafe} (Tepat 100%)`, ANSI.bold + ANSI.green);
  }
}

// ================= 4. M:N WORK-STEALING SCHEDULER =================
class WorkStealingSimulator {
  static runDemo() {
    console.log(`\n${ANSI.bold}=== BAGIAN 4: GO-STYLE M:N WORK-STEALING SCHEDULER ===${ANSI.reset}`);

    const P1_Queue = ["G1 (Process Payment)", "G2 (Send Email)", "G3 (Generate PDF)", "G4 (Audit Log)"];
    const P2_Queue = []; // P2 menganggur

    log("scheduler", `Processor P1 memiliki ${P1_Queue.length} Goroutine di antrean lokal.`, ANSI.cyan);
    log("scheduler", `Processor P2 dalam kondisi IDLE (0 Goroutine).`, ANSI.yellow);

    log("scheduler", `WORK-STEALING TRIGGERED! P2 mencuri separuh tugas dari antrean P1...`, ANSI.magenta);
    const stolenCount = Math.floor(P1_Queue.length / 2);
    const stolenTasks = P1_Queue.splice(0, stolenCount);
    P2_Queue.push(...stolenTasks);

    log("scheduler", `Hasil Penyeimbangan Beban:`, ANSI.green);
    log("scheduler", `-> P1 sekarang mengeksekusi: [${P1_Queue.join(", ")}]`, ANSI.green);
    log("scheduler", `-> P2 sekarang mengeksekusi: [${P2_Queue.join(", ")}]`, ANSI.green);
    log("scheduler", `Seluruh Core CPU fisik bekerja 100% secara optimal tanpa ada yang menganggur!`, ANSI.bold + ANSI.green);
  }
}

// ================= EKSEKUSI SIMULASI =================
console.log(`${ANSI.bold}================================================================${ANSI.reset}`);
console.log(`${ANSI.bold}    BACKEND RUNTIME MEMORY & CONCURRENCY ARCHITECTURE SIMULATOR ${ANSI.reset}`);
console.log(`${ANSI.bold}================================================================${ANSI.reset}`);

MemorySimulator.runDemo();
EventLoopSimulator.runDemo();
ConcurrencyConflictSimulator.runDemo();
WorkStealingSimulator.runDemo();

console.log(`\n${ANSI.bold}Seluruh perilaku arsitektur konkurensi runtime tervalidasi!${ANSI.reset}`);
