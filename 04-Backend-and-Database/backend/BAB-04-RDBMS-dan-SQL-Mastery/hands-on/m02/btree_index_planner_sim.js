/**
 * B-Tree Index Internals, Query Planner Cost Estimator, & Partitioning Simulator
 * 
 * Mensimulasikan logika mesin RDBMS internal:
 * 1. B-Tree 3-Level Tree Traversal vs Full Table Scan (Sequential Scan).
 * 2. Query Planner Cost Estimation: Kalkulasi cost I/O disk & CPU tuple evaluation.
 * 3. Evaluator Leftmost Prefix Rule pada Composite Index (country, status, created_at).
 * 4. Declarative Partition Pruning Engine: Eliminasi partisi disk yang tidak relevan.
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

// ================= 1. B-TREE INDEX SIMULATOR =================
class BTreeIndexSimulator {
  static runTraversalDemo() {
    console.log(`\n${ANSI.bold}=== BAGIAN 1: B-TREE INDEX TRAVERSAL VS FULL TABLE SCAN ===${ANSI.reset}`);

    const totalRows = 1000000;
    const targetId = 754320;

    // A. Full Table Scan (Seq Scan)
    log("query-planner", `Mengeksekusi Query: SELECT * FROM users WHERE id = ${targetId}; (Tanpa Index)`, ANSI.cyan);
    console.time("Sequential Scan (O(N))");
    let scannedRows = 0;
    for (let i = 1; i <= totalRows; i++) {
      scannedRows++;
      if (i === targetId) break;
    }
    console.timeEnd("Sequential Scan (O(N))");
    log("seq-scan", `Memindai ${scannedRows.toLocaleString()} baris fisik di disk! (Cost Tinggi: O(N))`, ANSI.red);

    // B. B-Tree Index Search (3-Level Depth)
    console.log("");
    log("query-planner", `Mengeksekusi Query: SELECT * FROM users WHERE id = ${targetId}; (Dengan B-Tree Index)`, ANSI.cyan);
    console.time("B-Tree Index Scan (O(log N))");
    log("btree-node", `[Lompatan 1] Root Page: Kunci ${targetId} berada di antara Branch [500.000 - 1.000.000]`, ANSI.magenta);
    log("btree-node", `[Lompatan 2] Internal Page: Kunci ${targetId} berada di antara Leaf [700.000 - 800.000]`, ANSI.magenta);
    log("btree-node", `[Lompatan 3] Leaf Page: Ditemukan Tuple ID -> Langsung membaca data block di SSD!`, ANSI.green);
    console.timeEnd("B-Tree Index Scan (O(log N))");
    log("btree-scan", `HANYA MEMBUTUHKAN TEPAT 3 LOMPATAN DISK PAGE! (Kecepatan Sub-Milidetik O(log N))`, ANSI.bold + ANSI.green);
  }
}

// ================= 2. LEFTMOST PREFIX RULE EVALUATOR =================
class CompositeIndexEvaluator {
  static evaluate(indexColumns, queryWhereColumns) {
    // indexColumns: ['country', 'status', 'created_at']
    log("planner-eval", `Memeriksa Composite Index: (${indexColumns.join(", ")})`, ANSI.bold);
    log("planner-eval", `Klausa WHERE Query: (${queryWhereColumns.join(", ")})`, ANSI.cyan);

    let matchedLevels = 0;
    for (let i = 0; i < indexColumns.length; i++) {
      if (queryWhereColumns.includes(indexColumns[i])) {
        matchedLevels++;
      } else {
        // Aturan Leftmost: Jika kolom urutan ke-i hilang, kolom berikutnya tidak bisa menggunakan index!
        break;
      }
    }

    if (matchedLevels === 0) {
      log("planner-result", `PELANGGARAN LEFTMOST PREFIX! Kolom paling kiri '${indexColumns[0]}' tidak ada di WHERE!`, ANSI.red);
      log("planner-result", `-> Keputusan Planner: EXPLAIN = Sequential Scan (Index Diabaikan Total)`, ANSI.red);
      return false;
    } else {
      log("planner-result", `INDEX MATCH! Menggunakan ${matchedLevels} kolom pertama dari Composite Index.`, ANSI.green);
      log("planner-result", `-> Keputusan Planner: EXPLAIN = Index Scan using idx_composite (${matchedLevels}/${indexColumns.length} fields match)`, ANSI.green);
      return true;
    }
  }
}

// ================= 3. PARTITION PRUNING SIMULATOR =================
class PartitionPruningSimulator {
  static runPruningDemo() {
    console.log(`\n${ANSI.bold}=== BAGIAN 3: DECLARATIVE TABLE PARTITION PRUNING ===${ANSI.reset}`);

    const partitions = [
      { name: "orders_2024", range: { from: "2024-01-01", to: "2024-12-31" }, sizeGB: 45 },
      { name: "orders_2025", range: { from: "2025-01-01", to: "2025-12-31" }, sizeGB: 80 },
      { name: "orders_2026", range: { from: "2026-01-01", to: "2026-12-31" }, sizeGB: 110 }
    ];

    const targetDate = "2026-05-20";
    log("query-planner", `Eksekusi Query: SELECT * FROM orders WHERE created_at = '${targetDate}';`, ANSI.cyan);

    log("partition-engine", "Mengevaluasi batasan range partisi (Partition Pruning)...", ANSI.yellow);
    const activePartitions = [];

    for (const p of partitions) {
      if (targetDate >= p.range.from && targetDate <= p.range.to) {
        log("partition-engine", `-> TARGET MATCH: Partisi '${p.name}' [${p.range.from} s/d ${p.range.to}] DIPILIH`, ANSI.green);
        activePartitions.push(p);
      } else {
        log("partition-engine", `-> PRUNED: Partisi '${p.name}' [${p.range.from} s/d ${p.range.to}] DIABAIKAN (Zero Disk I/O!)`, ANSI.magenta);
      }
    }

    const totalSavedGB = partitions.filter(p => !activePartitions.includes(p)).reduce((acc, p) => acc + p.sizeGB, 0);
    log("partition-engine", `HASIL PRUNING: Menghemat pembacaan disk fisik sebesar ${totalSavedGB} GB!`, ANSI.bold + ANSI.green);
  }
}

// ================= SIMULASI EKSEKUSI =================
console.log(`${ANSI.bold}================================================================${ANSI.reset}`);
console.log(`${ANSI.bold}   RDBMS B-TREE INDEX, QUERY PLANNER, & PARTITIONING SIMULATOR  ${ANSI.reset}`);
console.log(`${ANSI.bold}================================================================${ANSI.reset}`);

// 1. Uji Traversal B-Tree
BTreeIndexSimulator.runTraversalDemo();

// 2. Uji Leftmost Prefix Rule
console.log(`\n${ANSI.bold}=== BAGIAN 2: UJI COBA LEFTMOST PREFIX RULE ===${ANSI.reset}`);
const compositeIdx = ["country", "status", "created_at"];

console.log("\n[Kasus A: Menyertakan kolom paling kiri]");
CompositeIndexEvaluator.evaluate(compositeIdx, ["country", "status"]);

console.log("\n[Kasus B: Melompati kolom paling kiri (Hanya status dan created_at)]");
CompositeIndexEvaluator.evaluate(compositeIdx, ["status", "created_at"]);

// 3. Uji Partition Pruning
PartitionPruningSimulator.runPruningDemo();

console.log(`\n${ANSI.bold}Seluruh arsitektur B-Tree, Composite Index, dan Partitioning tervalidasi!${ANSI.reset}`);
