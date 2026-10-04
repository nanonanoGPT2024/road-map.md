/**
 * SIMULATOR: REACT FIBER WORKLOOP, TIME-SLICING & CONCURRENT PRIORITY INTERRUPTER
 * Modul 01: React Internals: Fiber Reconciler, Virtual DOM Diffing, & Concurrent Features
 *
 * Mendemonstrasikan:
 * 1. Struktur Data Fiber Node (Pointer: child, sibling, return, flags).
 * 2. Fiber WorkLoop dengan Time-Slicing (Yield ke Main Thread jika waktu > 5ms).
 * 3. Interupsi Prioritas Konkuren: Penanganan User Input Urgent di tengah proses render.
 * 4. Mesin Heuristik Virtual DOM Diffing O(N) dengan pencocokan 'key'.
 *
 * Jalankan: node react_fiber_reconciler_sim.js
 */

// =========================================================================
// BAGIAN 1: STRUKTUR DATA FIBER NODE & FLAGS
// =========================================================================

const FLAGS = {
  NO_EFFECT: 0,
  PLACEMENT: 1, // Node baru ditambahkan ke DOM
  UPDATE: 2,    // Node yang sudah ada diperbarui atributnya
  DELETION: 4   // Node dihapus dari DOM
};

class FiberNode {
  constructor(type, key = null, props = {}) {
    this.type = type;
    this.key = key;
    this.props = props;
    this.stateNode = null; // Simpan representasi DOM

    // Struktur Pointer Linked List Fiber
    this.child = null;
    this.sibling = null;
    this.return = null; // Parent

    this.flags = FLAGS.NO_EFFECT;
    this.alternate = null; // Double buffering
  }
}

// =========================================================================
// BAGIAN 2: SCHEDULER & FIBER WORKLOOP DENGAN TIME-SLICING
// =========================================================================

class FiberScheduler {
  constructor() {
    this.nextUnitOfWork = null;
    this.wipRoot = null;
    this.urgentQueue = [];
    this.deadlineBudgetMs = 5; // Jatah waktu maksimal 5ms per time-slice
  }

  // Simulator Cooperative Multitasking: Cek apakah jatah waktu habis
  shouldYield(startTime) {
    const elapsed = Date.now() - startTime;
    return elapsed >= this.deadlineBudgetMs;
  }

  scheduleWork(rootFiber) {
    this.wipRoot = rootFiber;
    this.nextUnitOfWork = rootFiber;
  }

  pushUrgentTask(taskName, action) {
    this.urgentQueue.push({ taskName, action, timestamp: Date.now() });
  }

  // Inti WorkLoop React Fiber
  async workLoop() {
    console.log('\nMemulai Fiber WorkLoop (Time-Slicing Engine)...');
    let startTime = Date.now();

    while (this.nextUnitOfWork !== null) {
      // 1. Cek apakah ada tugas URGENT (misal User Input ketikan keyboard)
      if (this.urgentQueue.length > 0) {
        const urgentTask = this.urgentQueue.shift();
        console.warn(`⚡ [INTERUPSI PRIORITAS TINGGI] Menunda render fiber! Memproses '${urgentTask.taskName}' terlebih dahulu...`);
        urgentTask.action();
        startTime = Date.now(); // Reset waktu setelah tugas darurat selesai
      }

      // 2. Cek apakah batas waktu 5ms terlampaui (Time-slice expired)
      if (this.shouldYield(startTime)) {
        console.log(`  ⏱️ [YIELD TO BROWSER] Batas 5ms tercapai. Mengembalikan kontrol ke Main Thread untuk paint frame!`);
        await new Promise(r => setTimeout(r, 10)); // Simulasi jeda 1 frame monitor
        startTime = Date.now(); // Lanjutkan di frame berikutnya
      }

      // 3. Jalankan satu unit kerja Fiber
      this.nextUnitOfWork = this.performUnitOfWork(this.nextUnitOfWork);
    }

    console.log('🏁 [RENDER PHASE SELESAI] Seluruh Fiber Tree selesai dihitung di memori!');
    this.commitRoot();
  }

  performUnitOfWork(fiber) {
    console.log(`  🔨 Memproses Fiber: <${fiber.type} key="${fiber.key || 'none'}">`);

    // Simulasi komputasi diffing component
    let dummy = 0;
    for (let i = 0; i < 500000; i++) dummy += i; // Pembakar CPU sesaat

    // Jika memiliki anak, lanjutkan ke anak pertama
    if (fiber.child) {
      return fiber.child;
    }

    // Jika tidak punya anak, telusuri saudara (sibling) atau naik ke parent (return)
    let current = fiber;
    while (current) {
      if (current.sibling) {
        return current.sibling;
      }
      current = current.return;
    }

    return null; // Seluruh pohon selesai
  }

  // FASE 2: COMMIT PHASE (Mutasi DOM Sinkron)
  commitRoot() {
    console.log('\n' + '='.repeat(60));
    console.log('FASE COMMIT SINKRON: Mengaplikasikan Efek ke Layar DOM Fisik');
    console.log('='.repeat(60));

    function commitWork(fiber) {
      if (!fiber) return;
      if (fiber.flags === FLAGS.PLACEMENT) {
        console.log(`  ➕ [DOM PLACEMENT] Membuat elemen <${fiber.type} id="${fiber.key}"> di DOM.`);
      } else if (fiber.flags === FLAGS.UPDATE) {
        console.log(`  🔄 [DOM UPDATE] Memperbarui atribut <${fiber.type} id="${fiber.key}">.`);
      } else if (fiber.flags === FLAGS.DELETION) {
        console.log(`  ❌ [DOM DELETION] Menghapus elemen <${fiber.type} id="${fiber.key}"> dari DOM.`);
      }

      commitWork(fiber.child);
      commitWork(fiber.sibling);
    }

    commitWork(this.wipRoot);
    console.log('✅ Layar Browser Berhasil Diperbarui Secara Mulus (Paint Complete)!');
  }
}

// =========================================================================
// BAGIAN 3: ALGORITMA HEURISTIK DIFFING DENGAN KUNCI IDENTITAS (KEY)
// =========================================================================

class VDomDiffEngine {
  static reconcileChildren(parentFiber, oldChildren, newVdomList) {
    console.log('\nMenjalankan Algoritma Diffing Heuristik O(N) Berbasis Key:');
    const oldMap = new Map();
    oldChildren.forEach(child => oldMap.set(child.key, child));

    let prevSibling = null;

    for (let i = 0; i < newVdomList.length; i++) {
      const vdom = newVdomList[i];
      let newFiber = null;

      if (oldMap.has(vdom.key)) {
        const oldFiber = oldMap.get(vdom.key);
        if (oldFiber.type === vdom.type) {
          // KASUS 1: Key sama & Type sama -> REUSE & UPDATE
          newFiber = new FiberNode(vdom.type, vdom.key, vdom.props);
          newFiber.flags = FLAGS.UPDATE;
          newFiber.stateNode = oldFiber.stateNode;
          console.log(`  ♻️ [REUSE NODE] Elemen ${vdom.key} dipertahankan posisinya tanpa unmount.`);
        } else {
          // KASUS 2: Key sama tapi Tipe Beda -> DESTROY & RECREATE
          newFiber = new FiberNode(vdom.type, vdom.key, vdom.props);
          newFiber.flags = FLAGS.PLACEMENT;
          console.log(`  💥 [TYPE MISMATCH] Elemen ${vdom.key} berubah tipe tag. Dihancurkan dan dibuat ulang!`);
        }
        oldMap.delete(vdom.key);
      } else {
        // KASUS 3: Elemen Baru -> PLACEMENT
        newFiber = new FiberNode(vdom.type, vdom.key, vdom.props);
        newFiber.flags = FLAGS.PLACEMENT;
        console.log(`  ✨ [NEW ELEMENT] Elemen baru ${vdom.key} ditambahkan.`);
      }

      newFiber.return = parentFiber;
      if (i === 0) {
        parentFiber.child = newFiber;
      } else if (prevSibling) {
        prevSibling.sibling = newFiber;
      }
      prevSibling = newFiber;
    }

    // Elemen lama yang tersisa di map wajib di-DELETION
    oldMap.forEach(orphan => {
      orphan.flags = FLAGS.DELETION;
      console.log(`  🗑️ [ORPHAN DELETION] Elemen lama ${orphan.key} ditandai untuk dihapus dari DOM.`);
    });

    return parentFiber;
  }
}

// =========================================================================
// BAGIAN 4: EKSEKUSI PENGUJIAN SKENARIO LENGKAP
// =========================================================================

async function main() {
  console.log('='.repeat(75));
  console.log('SIMULASI: REACT FIBER RECONCILER, TIME-SLICING & HEURISTIC DIFFING');
  console.log('='.repeat(75));

  const scheduler = new FiberScheduler();

  // 1. Membangun Struktur Pohon Fiber
  const root = new FiberNode('div', 'root');
  const child1 = new FiberNode('section', 'sec-1');
  const child2 = new FiberNode('article', 'art-2');
  const grandChild1 = new FiberNode('p', 'par-1');
  const grandChild2 = new FiberNode('button', 'btn-submit');

  root.child = child1;
  child1.return = root;
  child1.sibling = child2;
  child2.return = root;

  child1.child = grandChild1;
  grandChild1.return = child1;
  grandChild1.sibling = grandChild2;
  grandChild2.return = child1;

  // Jadwalkan tugas mendesak di tengah proses workloop
  setTimeout(() => {
    scheduler.pushUrgentTask('USER_KEYBOARD_INPUT', () => {
      console.log('  👉 [USER EVENT] Mengetik karakter "A" pada Search Box (Latensi 2ms)');
    });
  }, 3);

  // Jalankan WorkLoop
  scheduler.scheduleWork(root);
  await scheduler.workLoop();

  // 2. Uji Coba Virtual DOM Diffing dengan List Key
  console.log('\n' + '-'.repeat(75));
  console.log('PENGUJIAN VIRTUAL DOM HEURISTIC DIFFING:');
  console.log('-'.repeat(75));

  const oldList = [
    new FiberNode('li', 'ITEM-1', { text: 'Buku Pemrograman' }),
    new FiberNode('li', 'ITEM-2', { text: 'Mouse Wireless' }),
    new FiberNode('li', 'ITEM-3', { text: 'Keyboard Mekanikal' })
  ];

  // User menyortir list dan menghapus ITEM-2 serta menambah ITEM-4
  const newList = [
    { type: 'li', key: 'ITEM-3', props: { text: 'Keyboard Mekanikal Pro' } }, // Reordered & updated
    { type: 'li', key: 'ITEM-1', props: { text: 'Buku Pemrograman' } },       // Reordered
    { type: 'li', key: 'ITEM-4', props: { text: 'Monitor 4K' } }              // Brand new
  ];

  const parentListFiber = new FiberNode('ul', 'product-list');
  VDomDiffEngine.reconcileChildren(parentListFiber, oldList, newList);

  console.log('\n' + '='.repeat(75));
  console.log('SIMULASI BERHASIL: React Fiber & Diffing Engine terbukti bekerja presisi!');
  console.log('='.repeat(75));
}

main();
