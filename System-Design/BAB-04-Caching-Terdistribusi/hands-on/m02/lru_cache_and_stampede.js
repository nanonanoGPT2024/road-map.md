// lru_cache_and_stampede.js
// Implementasi Struktur Data LRU Cache O(1) & Simulasi Mitigasi Cache Stampede dengan Mutex Lock

// ===================================================================
// 1. STRUKTUR DATA LRU CACHE MURNI O(1) (DOUBLY LINKED LIST + HASH MAP)
// ===================================================================
class DNode {
  constructor(key, value) {
    this.key = key;
    this.value = value;
    this.prev = null;
    this.next = null;
  }
}

class LRUCache {
  constructor(capacity) {
    this.capacity = capacity;
    this.map = new Map(); // key -> DNode

    // Dummy Head dan Tail untuk mempermudah manipulasi pointer
    this.head = new DNode(0, 0);
    this.tail = new DNode(0, 0);
    this.head.next = this.tail;
    this.tail.prev = this.head;
  }

  // Tambahkan node baru tepat setelah Head (Most Recently Used)
  _addNode(node) {
    node.prev = this.head;
    node.next = this.head.next;
    this.head.next.prev = node;
    this.head.next = node;
  }

  // Cabut node dari posisi linked list
  _removeNode(node) {
    const prevNode = node.prev;
    const nextNode = node.next;
    prevNode.next = nextNode;
    nextNode.prev = prevNode;
  }

  // Pindahkan node yang baru diakses ke depan (Head)
  _moveToHead(node) {
    this._removeNode(node);
    this._addNode(node);
  }

  // Ambil data dalam O(1)
  get(key) {
    if (!this.map.has(key)) return null;
    const node = this.map.get(key);
    this._moveToHead(node); // Tandai sebagai baru diakses
    return node.value;
  }

  // Masukkan data dalam O(1), lakukan eviction jika penuh
  put(key, value) {
    if (this.map.has(key)) {
      const node = this.map.get(key);
      node.value = value;
      this._moveToHead(node);
    } else {
      const newNode = new DNode(key, value);
      this.map.set(key, newNode);
      this._addNode(newNode);

      // Jika kapasitas terlampaui, gusur node tertua di dekat Tail
      if (this.map.size > this.capacity) {
        const lruNode = this.tail.prev;
        this._removeNode(lruNode);
        this.map.delete(lruNode.key);
        console.log(`   [LRU EVICT]: Kapasitas penuh! Menggusur item paling lama tidak diakses: "${lruNode.key}"`);
      }
    }
  }

  printState() {
    const items = [];
    let curr = this.head.next;
    while (curr !== this.tail) {
      items.push(`${curr.key}:${curr.value}`);
      curr = curr.next;
    }
    console.log(`   Status Cache (Head/Baru -> Tail/Lama): [ ${items.join(" <-> ")} ] (Ukuran: ${this.map.size}/${this.capacity})`);
  }
}

// ===================================================================
// 2. SIMULATOR CACHE STAMPEDE vs MUTEX SINGLEFLIGHT MITIGATION
// ===================================================================
let dbQueryExecutionCount = 0;

// Simulasi Database Query yang Berat (~80ms)
function queryDatabaseHeavy() {
  dbQueryExecutionCount++;
  return new Promise(resolve => {
    setTimeout(() => {
      resolve({ product: "iPhone 16 Pro", price: 999 });
    }, 80);
  });
}

// Skenario A: Tanpa Proteksi Mutex (Stampede Terjadi)
async function fetchWithoutProtection(requestId) {
  // Semua request mendapati cache kosong dan serentak query ke database
  const res = await queryDatabaseHeavy();
  return { reqId: requestId, status: "DB Hit (No Protection)" };
}

// Skenario B: Dengan Mutex Singleflight
let isLockAcquired = false;
let ongoingPromise = null;
let sharedCacheValue = null;

async function fetchWithMutexSingleflight(requestId) {
  // Jika cache ada, langsung return
  if (sharedCacheValue) {
    return { reqId: requestId, status: "Cache HIT (Instant)", data: sharedCacheValue };
  }

  // Jika belum ada request yang mengambil lock, ambil hak query DB
  if (!isLockAcquired) {
    isLockAcquired = true;
    console.log(`   -> [Req #${requestId}] Berhasil mendapatkan Mutex Lock! Mengambil data ke Database...`);
    ongoingPromise = queryDatabaseHeavy().then(data => {
      sharedCacheValue = data;
      isLockAcquired = false;
      return data;
    });
  } else {
    console.log(`   -> [Req #${requestId}] Menunggu (Shared Lock aktif)...`);
  }

  // Seluruh request yang datang bersamaan memegang promise yang sama!
  const result = await ongoingPromise;
  return { reqId: requestId, status: "Resolved via Singleflight", data: result };
}

// ===================================================================
// RUN DEMO
// ===================================================================
async function runDemo() {
  console.log("===================================================================");
  console.log("   DEMO BAGIAN 1: STRUKTUR DATA LRU CACHE O(1) DENGAN KAPASITAS 3  ");
  console.log("===================================================================");

  const lru = new LRUCache(3);
  console.log("1. Memasukkan Kunci A, B, C:");
  lru.put("A", 100);
  lru.put("B", 200);
  lru.put("C", 300);
  lru.printState();

  console.log("\n2. Mengakses Kunci 'A' (A menjadi Most Recently Used / Head):");
  lru.get("A");
  lru.printState();

  console.log("\n3. Memasukkan Kunci Baru 'D' (Harus menggusur 'B' yang ada di Tail):");
  lru.put("D", 400);
  lru.printState();

  console.log("\n===================================================================");
  console.log("   DEMO BAGIAN 2: SIMULASI CACHE STAMPEDE vs MUTEX SINGLEFLIGHT   ");
  console.log("===================================================================");

  // UJI TANPA PROTEKSI
  console.log("\n--- UJI 1: 8 Request Konkuren TANPA Proteksi Mutex ---");
  dbQueryExecutionCount = 0;
  const unprotectPromises = [];
  for (let i = 1; i <= 8; i++) unprotectPromises.push(fetchWithoutProtection(i));
  await Promise.all(unprotectPromises);
  console.log(`💥 HASIL TANPA PROTEKSI: Database dihujani ${dbQueryExecutionCount} query SQL secara serentak!`);

  // UJI DENGAN MUTEX SINGLEFLIGHT
  console.log("\n--- UJI 2: 8 Request Konkuren DENGAN Proteksi Mutex Singleflight ---");
  dbQueryExecutionCount = 0;
  sharedCacheValue = null;
  isLockAcquired = false;
  const protectPromises = [];
  for (let i = 1; i <= 8; i++) protectPromises.push(fetchWithMutexSingleflight(i));
  await Promise.all(protectPromises);
  console.log(`\n🛡️ HASIL DENGAN MUTEX: Database HANYA menerima ${dbQueryExecutionCount} query SQL!`);
  console.log(`   7 request lainnya otomatis di-share responnya tanpa menyentuh database sama sekali.`);

  console.log("\n===================================================================");
  console.log(" [KESIMPULAN DEMO]:");
  console.log(" 1. LRU Cache berhasil menjaga batas kapasitas RAM dengan evicting data terlama.");
  console.log(" 2. Mutex Singleflight sukses mengeliminasi 87.5% beban query database berlebih.");
  console.log("===================================================================\n");
}

runDemo();
