// sql_vs_nosql_benchmark.js
// Benchmark Performa: Relational Multi-Table JOIN vs NoSQL Denormalized Document Fetch

const TOTAL_ORDERS = 50000;
const TARGET_ORDER_ID = 48120;

console.log("===================================================================");
console.log(` MEMBUAT DATASET: ${TOTAL_ORDERS.toLocaleString()} ORDERS DENGAN RELASI DINORMALISASI`);
console.log("===================================================================\n");

// ===================================================================
// 1. STRUKTUR RELASIONAL (SQL NORMALIZED: 3 TABEL TERPISAH)
// ===================================================================
const usersTable = new Map();
const ordersTable = [];
const orderItemsTable = [];

// Isi 5.000 user
for (let i = 1; i <= 5000; i++) {
  usersTable.set(i, { id: i, name: `User_${i}`, tier: i % 5 === 0 ? "Gold" : "Standard" });
}

// Isi 50.000 order & 150.000 items
for (let i = 1; i <= TOTAL_ORDERS; i++) {
  const userId = (i % 5000) + 1;
  ordersTable.push({ orderId: i, userId: userId, orderDate: "2026-09-11", status: "COMPLETED" });

  // Tiap order punya 3 items
  orderItemsTable.push({ id: i * 3 - 2, orderId: i, product: "Item A", qty: 1, price: 50 });
  orderItemsTable.push({ id: i * 3 - 1, orderId: i, product: "Item B", qty: 2, price: 25 });
  orderItemsTable.push({ id: i * 3, orderId: i, product: "Item C", qty: 1, price: 100 });
}

// ===================================================================
// 2. STRUKTUR NOSQL DOCUMENT (DENORMALIZED MONGODB STYLE)
// ===================================================================
// Seluruh informasi user, order, dan list items sudah tersimpan dalam 1 dokumen JSON tunggal
const nosqlDocumentStore = new Map();

for (let i = 1; i <= TOTAL_ORDERS; i++) {
  const userId = (i % 5000) + 1;
  nosqlDocumentStore.set(i, {
    orderId: i,
    customer: { id: userId, name: `User_${userId}`, tier: userId % 5 === 0 ? "Gold" : "Standard" },
    orderDate: "2026-09-11",
    status: "COMPLETED",
    items: [
      { product: "Item A", qty: 1, price: 50 },
      { product: "Item B", qty: 2, price: 25 },
      { product: "Item C", qty: 1, price: 100 }
    ],
    totalAmount: 200
  });
}

// ===================================================================
// BENCHMARK EXECUTION
// ===================================================================

// A. Relational Join Execution (Cari Order -> Join User -> Join OrderItems)
function executeRelationalJoin(orderId) {
  const start = process.hrtime.bigint();
  let comparisons = 0;

  // 1. Scan/Lookup Order
  let order = null;
  for (let i = 0; i < ordersTable.length; i++) {
    comparisons++;
    if (ordersTable[i].orderId === orderId) {
      order = ordersTable[i];
      break;
    }
  }

  // 2. Join User
  comparisons++;
  const user = usersTable.get(order.userId);

  // 3. Scan & Join Items (Membaca orderItemsTable)
  const items = [];
  for (let i = 0; i < orderItemsTable.length; i++) {
    comparisons++;
    if (orderItemsTable[i].orderId === orderId) {
      items.push(orderItemsTable[i]);
    }
  }

  const durationMicrosec = Number(process.hrtime.bigint() - start) / 1000;
  return {
    order,
    user,
    items,
    comparisons,
    durationMicrosec
  };
}

// B. NoSQL Document Fetch (Single O(1) Key Lookup)
function executeNoSQLFetch(orderId) {
  const start = process.hrtime.bigint();
  let comparisons = 1;

  // Single document retrieval
  const document = nosqlDocumentStore.get(orderId);

  const durationMicrosec = Number(process.hrtime.bigint() - start) / 1000;
  return {
    document,
    comparisons,
    durationMicrosec
  };
}

function runBenchmark() {
  console.log(`Mengambil data Invoice Lengkap untuk Order ID: ${TARGET_ORDER_ID}...\n`);

  // 1. Uji Relasional JOIN
  const sqlRes = executeRelationalJoin(TARGET_ORDER_ID);
  console.log(`[1. PENDEKATAN RELASIONAL (SQL MULTI-TABLE JOIN)]:`);
  console.log(` - Order ID        : ${sqlRes.order.orderId}`);
  console.log(` - Nama Customer   : ${sqlRes.user.name}`);
  console.log(` - Total Items     : ${sqlRes.items.length} produk`);
  console.log(` - Total Scan/Cek  : ${sqlRes.comparisons.toLocaleString()} iterasi perbandingan memori!`);
  console.log(` - Waktu Eksekusi  : ${sqlRes.durationMicrosec.toFixed(2)} mikrodetik (${(sqlRes.durationMicrosec / 1000).toFixed(3)} ms)\n`);

  // 2. Uji NoSQL Document Fetch
  const nosqlRes = executeNoSQLFetch(TARGET_ORDER_ID);
  console.log(`[2. PENDEKATAN NOSQL DOCUMENT (DENORMALIZED O(1))]:`);
  console.log(` - Order ID        : ${nosqlRes.document.orderId}`);
  console.log(` - Nama Customer   : ${nosqlRes.document.customer.name}`);
  console.log(` - Total Items     : ${nosqlRes.document.items.length} produk`);
  console.log(` - Total Scan/Cek  : HANYA ${nosqlRes.comparisons} kali lookup!`);
  console.log(` - Waktu Eksekusi  : ${nosqlRes.durationMicrosec.toFixed(2)} mikrodetik (${(nosqlRes.durationMicrosec / 1000).toFixed(3)} ms)\n`);

  console.log("===================================================================");
  console.log("                      KOMPARASI EFISIENSI                          ");
  console.log("===================================================================");
  const scanRatio = (sqlRes.comparisons / nosqlRes.comparisons).toFixed(0);
  const speedRatio = (sqlRes.durationMicrosec / nosqlRes.durationMicrosec).toFixed(1);
  console.log(`1. Reduksi Pemindaian Data : ${scanRatio}x lipat lebih sedikit!`);
  console.log(`2. Peningkatan Kecepatan   : ${speedRatio}x lipat lebih instan!`);
  console.log("===================================================================\n");
}

runBenchmark();
