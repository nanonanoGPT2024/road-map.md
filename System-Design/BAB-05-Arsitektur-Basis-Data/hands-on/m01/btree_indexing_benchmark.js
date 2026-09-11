// btree_indexing_benchmark.js
// Benchmark Performa: Full Table Scan O(N) vs B-Tree / Binary Index Lookup O(log N)

const TOTAL_RECORDS = 150000;
const TARGET_ID = 148920; // Target di dekat ujung akhir data

console.log("===================================================================");
console.log(` MEMBUAT DATASET SIMULASI: ${TOTAL_RECORDS.toLocaleString()} BARIS DATA`);
console.log("===================================================================\n");

// 1. Inisialisasi Data Tabel Fisik (Unsorted Raw Rows)
const rawTable = [];
for (let i = 1; i <= TOTAL_RECORDS; i++) {
  rawTable.push({
    id: i,
    username: `user_${i}`,
    email: `user_${i}@example.com`,
    balance: Math.floor(Math.random() * 5000)
  });
}

// 2. Inisialisasi B-Tree Index Simulator (Sorted Array of Keys + Pointer ke Row)
// Pada B+Tree nyata, ini tersusun dalam pohon berakar dengan fan-out tinggi
const btreeIndex = rawTable.map(row => ({ key: row.id, ref: row })).sort((a, b) => a.key - b.key);

// ===================================================================
// A. SIMULASI SEQUENTIAL FULL TABLE SCAN (O(N))
// ===================================================================
function executeSequentialScan(targetId) {
  let iterations = 0;
  const startTime = process.hrtime.bigint();

  let foundRow = null;
  for (let i = 0; i < rawTable.length; i++) {
    iterations++;
    if (rawTable[i].id === targetId) {
      foundRow = rawTable[i];
      break;
    }
  }

  const endTime = process.hrtime.bigint();
  const durationMicrosec = Number(endTime - startTime) / 1000;

  return { foundRow, iterations, durationMicrosec };
}

// ===================================================================
// B. SIMULASI B-TREE / BINARY SEARCH INDEX LOOKUP (O(log N))
// ===================================================================
function executeIndexLookup(targetId) {
  let iterations = 0;
  const startTime = process.hrtime.bigint();

  let low = 0;
  let high = btreeIndex.length - 1;
  let foundRow = null;

  while (low <= high) {
    iterations++;
    const mid = Math.floor((low + high) / 2);
    const midKey = btreeIndex[mid].key;

    if (midKey === targetId) {
      foundRow = btreeIndex[mid].ref; // Langsung akses baris via pointer
      break;
    } else if (midKey < targetId) {
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }

  const endTime = process.hrtime.bigint();
  const durationMicrosec = Number(endTime - startTime) / 1000;

  return { foundRow, iterations, durationMicrosec };
}

// ===================================================================
// RUN BENCHMARK
// ===================================================================
function runBenchmark() {
  console.log(`Mencari data dengan ID: ${TARGET_ID}...\n`);

  // Uji 1: Full Table Scan
  const seqRes = executeSequentialScan(TARGET_ID);
  console.log(`[1. FULL TABLE SCAN (Tanpa Index)]:`);
  console.log(` - Status Ditemukan : ${seqRes.foundRow ? 'YA' : 'TIDAK'}`);
  console.log(` - Total Baris Diperiksa: ${seqRes.iterations.toLocaleString()} baris!`);
  console.log(` - Waktu Eksekusi   : ${seqRes.durationMicrosec.toFixed(2)} mikrodetik (${(seqRes.durationMicrosec / 1000).toFixed(3)} ms)\n`);

  // Uji 2: B-Tree Index Lookup
  const idxRes = executeIndexLookup(TARGET_ID);
  console.log(`[2. B-TREE INDEX LOOKUP (O(log N))]:`);
  console.log(` - Status Ditemukan : ${idxRes.foundRow ? 'YA' : 'TIDAK'}`);
  console.log(` - Total Lompatan Node: HANYA ${idxRes.iterations} perbandingan!`);
  console.log(` - Waktu Eksekusi   : ${idxRes.durationMicrosec.toFixed(2)} mikrodetik (${(idxRes.durationMicrosec / 1000).toFixed(3)} ms)\n`);

  console.log("===================================================================");
  console.log("                      KOMPARASI EFISIENSI                          ");
  console.log("===================================================================");
  const inspectionRatio = (seqRes.iterations / idxRes.iterations).toFixed(0);
  const speedRatio = (seqRes.durationMicrosec / idxRes.durationMicrosec).toFixed(1);
  console.log(`1. Pengurangan Baris Diperiksa: ${inspectionRatio}x lipat lebih sedikit!`);
  console.log(`2. Peningkatan Kecepatan       : ${speedRatio}x lipat lebih kencang!`);
  console.log("===================================================================\n");
}

runBenchmark();
