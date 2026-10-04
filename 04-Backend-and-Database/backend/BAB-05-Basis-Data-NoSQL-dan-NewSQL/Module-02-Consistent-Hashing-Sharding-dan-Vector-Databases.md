---
[⬅️ Module 01: Taksonomi NoSQL & CAP](./Module-01-Taksonomi-NoSQL-CAP-Theorem-dan-Document-Stores.md) | [📋 Silabus Induk](../README.md) | [BAB 05 Quiz & Challenge ➡️](./BAB-05-Quiz-dan-Challenge.md)
---

# Module 02: Consistent Hashing, Sharding, Vector Databases, & NewSQL

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik mampu:
- Mengidentifikasi kegagalan fatal algoritma *Modulo Hashing* (`hash(key) % N`) saat penskalaan node dinamis dan membuktikan keunggulan matematis **Consistent Hashing**.
- Menguasai topologi **Consistent Hash Ring** dan teknik **Virtual Nodes (Vnodes)** guna menjamin distribusi beban merata (*Uniform Load Distribution*).
- Merancang formula **Quorum Consensus** ($R + W > N$) pada sistem terdistribusi untuk menyeimbangkan performa baca (*Read-heavy*) vs tulis (*Write-heavy*).
- Memahami arsitektur **Vector Databases** untuk kecerdasan buatan (AI) & Large Language Models (LLM): konsep *Vector Embeddings*, metrik jarak (*Cosine Similarity*, *Euclidean Distance*), dan algoritma *Approximate Nearest Neighbor (ANN)* (**HNSW** vs **IVF**).
- Membedakan NoSQL tradisional dengan paradigma **NewSQL** (Google Spanner, CockroachDB) yang menggabungkan skalabilitas horizontal NoSQL dengan jaminan transaksi ACID RDBMS.

---

## 2. Prerequisite
- Memahami Taksonomi NoSQL dan Teorema CAP (Modul 01).
- Pemahaman fungsi hash kriptografi (MD5, SHA-256, MurmurHash).
- Konsep dasar matematika aljabar linier (vektor, perkalian titik / dot product).

---

## 3. Concept
Ketika sebuah sistem database atau cache (seperti Redis Cluster, Cassandra, atau DynamoDB) menampung ratusan terabyte data, data tersebut tidak dapat disimpan di satu mesin fisik. Data harus dipecah dan didistribusikan ke puluhan hingga ribuan server (**Sharding**).

Tantangan terbesarnya adalah:
- **Bagaimana kita memetakan kunci data (misal: `user_id: 99120`) ke server tertentu tanpa perlu tabel pencarian raksasa?**
- Jika satu server mati atau kita menambahkan 5 server baru untuk menghadapi Black Friday, **bagaimana caranya agar kita tidak perlu memindahkan seluruh data cluster ke server lain?**

Jawabannya adalah algoritma **Consistent Hashing** (Karger et al., MIT 1997), yang menjadi pondasi dari seluruh sistem penyimpanan terdistribusi modern di dunia.

Di era Generative AI saat ini, kebutuhan penyimpanan berevolusi lebih jauh lagi: sistem tidak hanya menyimpan data teks atau angka, melainkan vektor matematika multidimensi (**Vector Databases**) untuk pencarian semantik kecerdasan buatan (*Semantic Search & Retrieval-Augmented Generation / RAG*).

```
+-----------------------------------------------------------------------------------+
|                        THE CONSISTENT HASH RING (0 to 2^32 - 1)                   |
|                                                                                   |
|                                      0                                            |
|                                [ Node-A (V1) ]                                    |
|                             /                   \                                 |
|                   [ Node-C (V2) ]           [ Node-B (V1) ]                       |
|                       /                               \                           |
|              Key "order-99"                      Key "user-45"                    |
|             (Falls clockwise                     (Falls clockwise                 |
|               into Node-A!)                        into Node-B!)                  |
|                      |                                 |                          |
|                      v                                 v                          |
|                 [ Node-A (V2) ]                   [ Node-C (V1) ]                 |
|                             \                   /                                 |
|                                [ Node-B (V2) ]                                    |
|                                                                                   |
|  * Kunci data dipetakan ke lingkaran hash dan disimpan di Node terdekat           |
|    searah jarum jam (Clockwise).                                                  |
|  * Jika Node baru ditambahkan, HANYA K/N kunci yang dipindahkan!                  |
+-----------------------------------------------------------------------------------+
```

---

## 4. Why?
Mengapa Consistent Hashing dan Vector Database menjadi topik wajib arsitektur modern?
1. **Mencegah Bencana Cache Collapse (Thundering Herd)**: Jika Anda menggunakan modulo hashing sederhana (`hash(key) % N`) pada 10 server cache, menambahkan 1 server baru akan mengubah modulo dari `% 10` menjadi `% 11`. Hasilnya: **91% kunci cache salah tempat**, memicu *cache miss 91%* serentak yang langsung meruntuhkan database primer Anda!
2. **Fondasi Sistem AI Modern (RAG & Semantic Search)**: Basis data relasional tidak bisa mencari *"artikel berita yang maknanya mirip dengan pertanyaan pengguna"*. Vector Database memungkinkan pencarian kemiripan arti di antara jutaan dokumen dalam waktu 5 milidetik.
3. **Pemberantasan Hotspot Data**: Virtual Nodes menjamin tidak ada satu server pun yang menampung beban 3x lipat lebih banyak dari server lainnya.

---

## 5. What?

### A. Modulo Hashing vs Consistent Hashing

#### Modulo Hashing Sederhana:
$$\text{Server Index} = \text{hash}(\text{key}) \pmod N$$
Jika $N = 4$ server, key dengan hash 14 akan masuk ke server $14 \pmod 4 = 2$.
Jika 1 server ditambahkan ($N = 5$), key tersebut sekarang dipetakan ke $14 \pmod 5 = 4$.
Hampir seluruh data di cluster harus dipindahkan! Rasio perpindahan data:
$$\text{Data Moved} = \frac{N}{N + 1} \approx 80\% - 99\%$$

#### Consistent Hashing:
Ruang hash dipetakan ke lingkaran tertutup berukuran $2^{32} - 1$.
Kunci data berjalan searah jarum jam (*clockwise*) hingga menemukan node server pertama.
Ketika 1 server ditambahkan ke cluster berisi $N$ node, **HANYA $\frac{1}{N + 1}$ kunci yang dipindahkan** (hanya kunci tetangga langsungnya!). Seluruh server lainnya tidak terganggu.

#### Peran Virtual Nodes (Vnodes):
Jika kita hanya menaruh 3 node fisik pada lingkaran, jarak antar node bisa sangat tidak simetris (satu node menampung 70% lingkaran).
Solusi: Setiap mesin fisik direpresentasikan oleh **100 hingga 256 Virtual Nodes** yang tersebar acak di sepanjang lingkaran. Ini menghasilkan distribusi beban yang presisi dan merata.

---

### B. Rumus Quorum Terdistribusi ($N, W, R$)
Pada sistem penyimpanan NoSQL terdistribusi (Cassandra, DynamoDB):
- **$N$**: Faktor Replikasi (*Replication Factor*) — berapa banyak copy data disimpan di node berbeda.
- **$W$**: Write Quorum — berapa banyak node yang harus mengonfirmasi penulisan sukses sebelum client menerima `OK`.
- **$R$**: Read Quorum — berapa banyak node yang harus dibaca untuk menentukan data terkini.

> [!IMPORTANT]
> **Aturan Konsistensi Kuat (Strong Consistency)**:
> $$R + W > N$$
> Jika persamaan di atas terpenuhi, dijamin bahwa himpunan node yang dibaca ($R$) dan himpunan node yang ditulis ($W$) **selalu bertumpuk (overlap) minimal pada 1 node** yang memegang data versi terbaru!

*Contoh Tuning Praktis ($N = 3$)*:
1. **Strong Consistency Seimbang**: $W = 2$, $R = 2$ ($2 + 2 = 4 > 3$). Toleran terhadap kegagalan 1 node.
2. **Fast Write, Slow Read**: $W = 1$, $R = 3$ ($1 + 3 = 4 > 3$). Tulis secepat kilat, namun pembacaan harus membaca seluruh 3 node.
3. **Fast Read, Slow Write**: $W = 3$, $R = 1$ ($3 + 1 = 4 > 3$). Sempurna untuk sistem read-heavy yang jarang di-update.

---

### C. Vector Databases untuk AI: Konsep Dasar
Data teks, gambar, atau audio diubah oleh model AI (seperti OpenAI `text-embedding-3-small`) menjadi array angka mengambang berkoma (*Floating-Point Vector* berdimensi 1536):
$$\vec{v} = [0.0124, -0.0481, 0.0892, \dots, -0.0031]$$

#### 1. Metrik Jarak (Distance Metrics):
- **Cosine Similarity**: Mengukur sudut kosinus antara dua vektor (rentang -1 hingga 1). 1 berarti makna dokumen identik, tidak terpengaruh oleh panjang teks:
  $$\text{Cosine}(\vec{u}, \vec{v}) = \frac{\vec{u} \cdot \vec{v}}{\|\vec{u}\| \|\vec{v}\|}$$
- **Euclidean Distance ($L_2$)**: Jarak geometris lurus antar titik.

#### 2. Algoritma Indeks ANN (Approximate Nearest Neighbor):
Mencari vektor terdekat di antara 10 juta vektor secara brute-force ($O(N)$) memakan waktu terlalu lama. Digunakan algoritma aproksimasi:
- **HNSW (Hierarchical Navigable Small World)**: Standar emas industri. Membangun graf bertingkat multi-layer (mirip struktur Skip-List). Pencarian melompat dari layer teratas yang jarang menuju layer terbawah yang padat dengan kompleksitas waktu $O(\log N)$!

---

## 6. How?

### Pencarian Vektor Menggunakan Ekstensi `pgvector` di PostgreSQL

PostgreSQL dapat bertransformasi menjadi Vector Database kelas dunia hanya dengan mengaktifkan ekstensi `pgvector`:

```sql
-- 1. Aktifkan ekstensi
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Buat tabel knowledge base dengan kolom embedding 1536 dimensi
CREATE TABLE document_sections (
    id BIGSERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(1536) -- Format vektor densitas tinggi
);

-- 3. Buat Index HNSW untuk pencarian berkecepatan tinggi
CREATE INDEX idx_sections_hnsw ON document_sections 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- 4. Pencarian Semantik (Cari 5 dokumen paling relevan dengan query pengguna)
-- Operator <=> adalah Cosine Distance
SELECT id, content, 1 - (embedding <=> '[0.012, -0.045, ...]') AS similarity_score
FROM document_sections
ORDER BY embedding <=> '[0.012, -0.045, ...]' ASC
LIMIT 5;
```

---

## 7. Analogy
Bayangkan **Pembagian Meja Tamu Pernikahan**:
- **Modulo Hashing**: Menyuruh tamu duduk berdasarkan nomor undangan modulo 4 meja. Jika Anda menambah Meja ke-5 di tengah acara, Anda menyuruh 80% tamu yang sedang makan untuk berdiri dan pindah meja! (**Kekacauan Total**).
- **Consistent Hashing**: Menyusun seluruh meja melingkar di aula bundar. Tamu yang masuk berjalan memutari aula dan duduk di kursi kosong pertama yang mereka temui. Jika Anda menyisipkan 1 meja baru di aula, hanya tamu di meja sebelahnya yang bergeser sedikit; tamu di seberang ruangan tetap duduk tenang (**Kerapian Sempurna**).
- **Vector Search (Embeddings)**: Bayangkan perpustakaan raksasa di mana buku tidak diurutkan berdasarkan abjad judul, melainkan diatur di ruang 3 dimensi berdasarkan "aura/makna isi buku". Buku tentang "Astronomi" berada di pojok yang berdekatan dengan "Fisika Kuantum", dan sangat jauh dari buku "Resep Membuat Kue". Saat Anda bertanya: *"Bagaimana bintang terbentuk?"*, pustakawan langsung berjalan ke pojok Astronomi tanpa membaca judul satu per satu.

---

## 8. Diagram: Hierarchical Navigable Small World (HNSW)

```
+---------------------------------------------------------------------------------+
|                       HNSW MULTI-LAYER GRAPH STRUCTURE                          |
+---------------------------------------------------------------------------------+

Layer 2 (Expressway - Few Nodes):
[ Query ] ---> ( Node A ) ---------------------------------> ( Node F )
                                                                |
                                                                v drops to Layer 1
Layer 1 (Local Roads):
               ( Node A ) --------> ( Node C ) ------------> ( Node F ) ---> ( Node H )
                                                                               |
                                                                               v drops
Layer 0 (Dense Footpaths - All Vectors):
               ( Node A ) <-> ( B ) <-> ( C ) <-> ( D ) <-> ( F ) <-> ( G ) <-> ( H )
                                                                                  ^
                                                                           [ BEST MATCH! ]

Kompleksitas Pencarian: O(log N)! Melompat cepat dari jarak jauh,
lalu menyempurnakan pencarian di lingkungan lokal.
```

---

## 9. Simple Example: Menghitung Cosine Similarity di JavaScript

```javascript
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

// Contoh Dua Vektor Dokumen AI (Dimensi 3 sederhana)
const doc1 = [0.9, 0.1, 0.05]; // Dokumen tentang "Teknologi"
const doc2 = [0.85, 0.15, 0.02]; // Dokumen tentang "Komputer"
const doc3 = [0.01, 0.05, 0.95]; // Dokumen tentang "Biologi"

console.log("Similarity Doc 1 vs Doc 2:", cosineSimilarity(doc1, doc2)); // ~0.99 (Sangat Mirip!)
console.log("Similarity Doc 1 vs Doc 3:", cosineSimilarity(doc1, doc3)); // ~0.08 (Sangat Berbeda!)
```

---

## 10. Practical Example: Mengonfigurasi Virtual Nodes pada Consistent Hash Ring

```javascript
const crypto = require('crypto');

class ConsistentHashRing {
  constructor(vnodes = 100) {
    this.vnodes = vnodes;
    this.ring = new Map(); // hashValue -> physicalNodeName
    this.sortedKeys = [];
  }

  _hash(str) {
    return parseInt(crypto.createHash('md5').update(str).digest('hex').substring(0, 8), 16);
  }

  addNode(nodeName) {
    for (let i = 0; i < this.vnodes; i++) {
      const vnodeKey = `${nodeName}#vnode-${i}`;
      const hash = this._hash(vnodeKey);
      this.ring.set(hash, nodeName);
      this.sortedKeys.push(hash);
    }
    this.sortedKeys.sort((a, b) => a - b);
  }

  getNode(key) {
    if (this.sortedKeys.length === 0) return null;
    const hash = this._hash(key);

    // Cari node pertama yang nilainya >= hash (Binary Search)
    let low = 0;
    let high = this.sortedKeys.length - 1;
    let targetIdx = 0;

    while (low <= high) {
      const mid = Math.floor((low + high) / 2);
      if (this.sortedKeys[mid] >= hash) {
        targetIdx = mid;
        high = mid - 1;
      } else {
        low = mid + 1;
      }
    }

    const matchedHash = this.sortedKeys[targetIdx] || this.sortedKeys[0]; // Wrap around
    return this.ring.get(matchedHash);
  }
}
```

---

## 11. Real World Example: NewSQL di Balik Google Spanner & CockroachDB
Selama bertahun-tahun industri meyakini dogma bahwa database terdistribusi multi-datacenter global harus memilih antara menjadi sistem RDBMS lambat atau sistem NoSQL ber-Eventual Consistency (*Teorema CAP*).
- Terobosan Google Spanner: Google membangun infrastruktur hardware jaringan khusus yang dilengkapi dengan **Atomic Clocks (Jam Atomik Cesium)** dan penerima GPS di setiap datacenter (**TrueTime API**).
- TrueTime menjamin batas ketidakpastian waktu antar server di seluruh dunia tidak pernah melebihi 7 milidetik ($\epsilon \le 7\text{ms}$).
- Dengan ketepatan waktu matematis ini, Spanner mampu mengeksekusi **Distributed ACID Transactions secara Serializable** di seluruh benua tanpa penguncian lambat, melahirkan kategori basis data baru: **NewSQL** (yang diadopsi secara open-source oleh **CockroachDB**).

---

## 12. Trade-offs

| Pendekatan Penyimpanan | Keunggulan Utama | Risiko / Batasan |
|---|---|---|
| **Consistent Hashing** | Skalabilitas node dinamis dengan migrasi data minimal | Kompleksitas penanganan virtual nodes & rebalancing |
| **HNSW Index (Vector)** | Kecepatan pencarian semantik sub-milidetik, akurasi tinggi | Membutuhkan RAM sangat besar (seluruh graf harus muat di RAM) |
| **Dedicated Vector DB (Pinecone)** | Manajemen otomatis, fitur filtering metadata canggih | Biaya cloud hosting tinggi, data terpisah dari relational DB |
| **PostgreSQL `pgvector`** | Satu database untuk data relasional + data vektor AI (ACID) | Performa query vektor berskala miliaran dokumen terbatas |

---

## 13. When To Use
- Gunakan **Consistent Hashing** saat membangun distributed cache ring (Redis), routing request di API Gateway, atau sharding database mandiri.
- Gunakan **`pgvector`** jika dataset dokumen AI Anda berada di bawah 1.000.000 vektor dan Anda ingin menggabungkan filter SQL relasional (`WHERE organization_id = 5`) dengan pencarian kemiripan vektor.
- Gunakan **Dedicated Vector DB (Milvus / Qdrant / Pinecone)** untuk dataset AI raksasa (> 10 juta vektor) dengan kebutuhan throughput pencarian semantik ribuan QPS.

---

## 14. When NOT To Use
- **JANGAN** menggunakan sharding berbasis rentang nilai (*Range-Based Sharding*, misal: Shard 1 untuk ID 1-1000, Shard 2 untuk 1001-2000) jika data Anda memiliki Primary Key auto-increment, karena 100% operasi penulisan data baru akan selalu menghantam shard terakhir (*Hotspot write bottleneck*).
- Jangan menggunakan Vector Database untuk pencarian teks kata kunci exact match (gunakan Elasticsearch atau B-Tree index).

---

## 15. Common Mistakes
1. **Lupa Normalisasi Vektor Sebelum Cosine Search**: Jika model embedding tidak menghasilkan unit vector (panjang = 1), menghitung Dot Product secara keliru akan menghasilkan skor kemiripan yang salah.
2. **Tidak Menggunakan Virtual Nodes**: Hanya menempatkan node fisik murni di lingkaran hash, menyebabkan distribusi data timpang (satu server menampung 60% beban dan kehabisan disk).
3. **Mengabaikan Parameter `ef_search` pada HNSW**: Menyetel parameter pencarian HNSW terlalu rendah menghasilkan akurasi pencarian (*recall rate*) yang buruk di mana jawaban paling relevan terlewatkan.

---

## 16. Best Practices
- **Must Have**: Tetapkan minimal 100 hingga 256 Virtual Nodes per mesin fisik pada implementasi Consistent Hashing.
- **Recommended**: Simpan metadata (seperti `user_id`, `created_at`) langsung berdampingan dengan vektor untuk memungkinkan *Pre-Filtering* atau *Post-Filtering* pencarian semantik.
- **Advanced**: Implementasikan formula Quorum $R + W > N$ dengan parameter `LOCAL_QUORUM` pada Apache Cassandra untuk menghindari penundaan replikasi lintas benua (*Cross-DC latency penalty*).
- **Avoid**: Melakukan komputasi jarak vektor brute-force ($O(N)$) pada tabel dengan lebih dari 10.000 dokumen tanpa index HNSW atau IVF.

---

## 17. Troubleshooting Guide
```
Masalah: Performa pencarian kemiripan pgvector sangat lambat (memakan waktu 3 detik per query).
Penyebab : Query Planner tidak menggunakan HNSW index dan melakukan pemindaian brute force (Sequential Scan).
Diagnosa : EXPLAIN ANALYZE SELECT ... ORDER BY embedding <=> '[...]' LIMIT 5;
           Jika muncul "Seq Scan", periksa apakah parameter 'maintenance_work_mem' cukup saat membuat index.
Solusi   : Naikkan batas memori dan bangun index HNSW:
           SET maintenance_work_mem = '2GB';
           CREATE INDEX ... USING hnsw (embedding vector_cosine_ops);

Masalah: Satu node Redis Cluster kehabisan memori sementara node lain masih kosong 70%.
Penyebab : Terjadi Hash Tag hotspot (misal ribuan key dibungkus dengan prefix {user_123} yang sama).
Solusi   : Audit distribusi key dan hindari penggunaan Hash Tag yang terlalu kasar agar kunci tersebar merata di sepanjang hash slots.
```

---

## 18. Exercise
1. Bangun simulator lingkaran hash sederhana dengan 3 node dan 50 virtual nodes per server.
2. Petakan 1.000 string kunci acak ke lingkaran hash tersebut dan catat distribusi persentase jumlah kunci di masing-masing dari 3 node.
3. Tambahkan node ke-4 dan buktikan bahwa hanya sebagian kecil kunci (~25%) yang berpindah kepemilikan.

---

## 19. Challenge
Rancang arsitektur Retrieval-Augmented Generation (RAG) untuk sistem pencarian dokumen internal perbankan (10.000.000 halaman PDF regulasi):
1. Rancang pipeline chunking teks dan pembangkitan embedding vektor.
2. Tentukan pilihan penyimpanan: PostgreSQL `pgvector` vs Dedicated Vector Database (Qdrant/Milvus), lengkap dengan analisis estimasi RAM server yang dibutuhkan untuk index HNSW.
3. Rancang strategi pembaruan dokumen real-time tanpa mengganggu latensi pencarian pengguna di produksi!

---

## 20. Summary
Consistent Hashing menghadirkan elastisitas tanpa batas bagi sistem penyimpanan data terdistribusi dengan meminimalkan migrasi data saat topologi berubah. Bersanding dengan teknologi Vector Databases yang mendefinisikan ulang cara sistem backend berinteraksi dengan kecerdasan buatan, seorang arsitek sistem dapat memadukan data terstruktur, semi-terstruktur, dan data semantik modern ke dalam satu ekosistem komputasi yang harmonis.

---
[⬅️ Module 01: Taksonomi NoSQL & CAP](./Module-01-Taksonomi-NoSQL-CAP-Theorem-dan-Document-Stores.md) | [📋 Silabus Induk](../README.md) | [BAB 05 Quiz & Challenge ➡️](./BAB-05-Quiz-dan-Challenge.md)
---
