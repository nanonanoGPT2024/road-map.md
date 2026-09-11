/**
 * SIMULATOR: CONSISTENT HASH RING DENGAN VNODES & VECTOR SIMILARITY ENGINE
 * Modul 02: Consistent Hashing, Sharding, Vector Databases, & NewSQL
 *
 * Mendemonstrasikan:
 * 1. Perbandingan Modulo Hashing (hash % N) vs Consistent Hashing saat node ditambah.
 * 2. Distribusi kunci merata dengan Virtual Nodes (Vnodes).
 * 3. Mesin kalkulasi Vector Similarity (Cosine Distance) untuk pencarian semantik (AI/LLM).
 *
 * Jalankan: node consistent_hashing_ring_sim.js
 */

const crypto = require('crypto');

function hashInt(str) {
  const hash = crypto.createHash('md5').update(String(str)).digest('hex');
  // Ambil 8 karakter pertama (32-bit integer unsigned)
  return parseInt(hash.substring(0, 8), 16);
}

// =========================================================================
// BAGIAN 1: PEMBUKTIAN KERUSAKAN MODULO HASHING SAAT SCALING
// =========================================================================
console.log('='.repeat(75));
console.log('BAGIAN 1: ANALISIS KEGAGALAN MODULO HASHING (hash(k) % N)');
console.log('='.repeat(75));

const sampleKeys = [];
for (let i = 0; i < 1000; i++) {
  sampleKeys.push(`session_token_${i}_${crypto.randomBytes(4).toString('hex')}`);
}

const initialNodesCount = 4;
const newNodesCount = 5; // Scaling up: tambah 1 node

let remappedKeysModulo = 0;
for (const key of sampleKeys) {
  const hashVal = hashInt(key);
  const oldNode = hashVal % initialNodesCount;
  const newNode = hashVal % newNodesCount;
  if (oldNode !== newNode) {
    remappedKeysModulo++;
  }
}

const moduloDisruptionRate = ((remappedKeysModulo / sampleKeys.length) * 100).toFixed(2);
console.log(`Jumlah Kunci Uji         : ${sampleKeys.length}`);
console.log(`Topologi Awal           : ${initialNodesCount} node`);
console.log(`Topologi Baru           : ${newNodesCount} node (+1 node)`);
console.log(`Kunci Terdisrupsi/Pindah: ${remappedKeysModulo} kunci (${moduloDisruptionRate}%)`);
console.log(`⚠️  KESIMPULAN MODULO    : Sebanyak ~${moduloDisruptionRate}% data kehilangan mapping!`);
console.log(`   Menyebabkan Cache Avalanche dan overload database masif!\n`);

// =========================================================================
// BAGIAN 2: KONSISTENSI TOPOLOGI DENGAN CONSISTENT HASH RING & VNODES
// =========================================================================
console.log('='.repeat(75));
console.log('BAGIAN 2: CONSISTENT HASH RING DENGAN VIRTUAL NODES (VNODES)');
console.log('='.repeat(75));

class ConsistentHashRing {
  constructor(vnodes = 100) {
    this.vnodes = vnodes;
    this.ring = []; // Array of { hash: number, physicalNode: string, vnodeId: string }
    this.nodes = new Set();
  }

  addNode(node) {
    this.nodes.add(node);
    for (let i = 0; i < this.vnodes; i++) {
      const vnodeId = `${node}#VN${i}`;
      const hash = hashInt(vnodeId);
      this.ring.push({ hash, physicalNode: node, vnodeId });
    }
    // Urutkan ring berdasarkan nilai hash (searah jarum jam)
    this.ring.sort((a, b) => a.hash - b.hash);
  }

  removeNode(node) {
    this.nodes.delete(node);
    this.ring = this.ring.filter(item => item.physicalNode !== node);
  }

  getNode(key) {
    if (this.ring.length === 0) return null;
    const hash = hashInt(key);

    // Binary search untuk mencari node pertama dengan hash >= key hash
    let low = 0;
    let high = this.ring.length - 1;
    let foundIndex = 0;

    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      if (this.ring[mid].hash >= hash) {
        foundIndex = mid;
        high = mid - 1; // Cari yang lebih kecil jika masih memenuhi
      } else {
        low = mid + 1;
      }
    }

    // Jika melebihi elemen terbesar, wrap-around ke indeks 0 (siklus lingkaran)
    if (low >= this.ring.length) {
      foundIndex = 0;
    }

    return this.ring[foundIndex].physicalNode;
  }
}

const ring = new ConsistentHashRing(100);
const physicalNodes = ['Node-A (10.0.0.1)', 'Node-B (10.0.0.2)', 'Node-C (10.0.0.3)', 'Node-D (10.0.0.4)'];
physicalNodes.forEach(n => ring.addNode(n));

console.log(`Membangun Ring dengan ${physicalNodes.length} Node Fisik x 100 Vnodes = ${ring.ring.length} total vnodes.`);

// Distribusikan 1000 kunci
const mappingBefore = new Map();
const nodeCountsBefore = {};
physicalNodes.forEach(n => nodeCountsBefore[n] = 0);

for (const key of sampleKeys) {
  const targetNode = ring.getNode(key);
  mappingBefore.set(key, targetNode);
  nodeCountsBefore[targetNode]++;
}

console.log('\nDistribusi Kunci Awal:');
for (const [node, count] of Object.entries(nodeCountsBefore)) {
  const pct = ((count / sampleKeys.length) * 100).toFixed(1);
  const bar = '█'.repeat(Math.round(pct / 2));
  console.log(`  ${node.padEnd(20)}: ${String(count).padStart(4)} kunci (${pct}%) ${bar}`);
}

// Tambahkan Node Baru: Node-E
const newNode = 'Node-E (10.0.0.5)';
console.log(`\nMenambahkan node baru secara dinamis: ${newNode}...`);
ring.addNode(newNode);

let remappedConsistent = 0;
const nodeCountsAfter = {};
[...physicalNodes, newNode].forEach(n => nodeCountsAfter[n] = 0);

for (const key of sampleKeys) {
  const targetNode = ring.getNode(key);
  nodeCountsAfter[targetNode]++;
  if (mappingBefore.get(key) !== targetNode) {
    remappedConsistent++;
  }
}

const consistentDisruptionRate = ((remappedConsistent / sampleKeys.length) * 100).toFixed(2);
console.log('\nDistribusi Kunci Setelah Penambahan Node-E:');
for (const [node, count] of Object.entries(nodeCountsAfter)) {
  const pct = ((count / sampleKeys.length) * 100).toFixed(1);
  const bar = '█'.repeat(Math.round(pct / 2));
  console.log(`  ${node.padEnd(20)}: ${String(count).padStart(4)} kunci (${pct}%) ${bar}`);
}

console.log(`\nKunci Terdisrupsi / Pindah: ${remappedConsistent} kunci (${consistentDisruptionRate}%)`);
console.log(`Teoritis migrasi ideal 1/(N+1) = ${(100 / 5).toFixed(2)}%`);
console.log(`✅ KESIMPULAN CONSISTENT HASHING: Hanya data milik node baru yang berpindah!`);
console.log(`   ~${(100 - consistentDisruptionRate).toFixed(2)}% data cache tetap utuh dan aman!\n`);

// =========================================================================
// BAGIAN 3: VECTOR SIMILARITY ENGINE (COSINE SIMILARITY UNTUK AI/LLM)
// =========================================================================
console.log('='.repeat(75));
console.log('BAGIAN 3: MESIN PENCARIAN VEKTOR (VECTOR EMBEDDINGS & COSINE SIMILARITY)');
console.log('='.repeat(75));

// Fungsi menghitung Cosine Similarity antara dua vektor
function cosineSimilarity(vecA, vecB) {
  let dotProduct = 0;
  let normA = 0;
  let normB = 0;
  for (let i = 0; i < vecA.length; i++) {
    dotProduct += vecA[i] * vecB[i];
    normA += vecA[i] * vecA[i];
    normB += vecB[i] * vecB[i];
  }
  if (normA === 0 || normB === 0) return 0;
  return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
}

// Simulasi database dokumen dengan representasi vektor embedding 4-dimensi
// Fitur dimensi: [finansial, keamanan, cloud, kecerdasan_buatan]
const vectorDatabase = [
  { id: 'DOC-01', title: 'Panduan Audit PCI-DSS & Enkripsi Kartu Kredit', vector: [0.92, 0.88, 0.15, 0.05] },
  { id: 'DOC-02', title: 'Penerapan Kubernetes & Microservices di AWS',   vector: [0.12, 0.45, 0.95, 0.20] },
  { id: 'DOC-03', title: 'Pelatihan Large Language Models & Deep Learning', vector: [0.08, 0.15, 0.60, 0.96] },
  { id: 'DOC-04', title: 'Mitigasi SQL Injection & API Security OWASP',   vector: [0.35, 0.94, 0.40, 0.12] },
  { id: 'DOC-05', title: 'Sistem Pembayaran Gateway & Ledger Transaksi',  vector: [0.95, 0.70, 0.30, 0.10] },
  { id: 'DOC-06', title: 'Pemanfaatan Vector Database Qdrant untuk RAG',   vector: [0.10, 0.25, 0.75, 0.92] }
];

// Query user: "Bagaimana cara mengamankan transaksi pembayaran online?"
// Vector embedding query hasil model AI:
const userQueryVector = [0.89, 0.85, 0.20, 0.08];
console.log('Query User: "Bagaimana cara mengamankan transaksi pembayaran online?"');
console.log('User Vector Embedding:', JSON.stringify(userQueryVector));
console.log('\nMelakukan pencarian Nearest Neighbor (K-NN) di Vector Database...\n');

const searchResults = vectorDatabase.map(doc => {
  const similarity = cosineSimilarity(userQueryVector, doc.vector);
  return {
    ...doc,
    similarity: Number(similarity.toFixed(4))
  };
}).sort((a, b) => b.similarity - a.similarity);

console.log('Peringkat Dokumen Paling Relevan (Top Nearest Neighbors):');
searchResults.forEach((res, rank) => {
  const scoreBar = '█'.repeat(Math.round(res.similarity * 25));
  console.log(`  #${rank + 1} [Skor: ${res.similarity.toFixed(4)}] ${scoreBar.padEnd(26)} : ${res.id} - ${res.title}`);
});

console.log('\n' + '='.repeat(75));
console.log('SIMULASI BERHASIL: Consistent Hashing & Vector Search berjalan sempurna!');
console.log('='.repeat(75));
