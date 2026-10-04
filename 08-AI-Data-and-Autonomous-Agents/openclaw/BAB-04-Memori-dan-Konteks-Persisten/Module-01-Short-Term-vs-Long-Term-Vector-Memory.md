# Module 01: Short-term Session vs Long-term Vector Memory

## 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
- Mengidentifikasi masalah "amnesia" pada LLM murni (*Stateless Inference*) dan bagaimana sistem memori menyelesaikannya.
- Membedakan peran **Short-term Working Memory** (buffer sesi percakapan di SQLite) dan **Long-term Semantic Memory** (vektor semantik).
- Memahami konsep **Vector Embeddings** dan pengukuran kesamaan semantik (*Cosine Similarity*).
- Menyimpan fakta personal, preferensi pengguna, dan peristiwa masa lalu (*Episodic Memory*) ke dalam basis data vektor lokal.

## 2. Prerequisite
- Memahami konsep token context window dan token limits dari BAB 02.
- Pengetahuan dasar tentang representasi array angka (vektor).

## 3. Concept
Secara alami, Large Language Model (LLM) tidak memiliki ingatan (*Stateless*). Setiap kali Anda mengirim pesan baru, model tidak mengetahui apa yang Anda katakan 5 menit yang lalu kecuali riwayat obrolan tersebut dikirimkan kembali ke dalam prompt.

Namun, memasukkan seluruh riwayat percakapan yang pernah terjadi selama 6 bulan ke dalam setiap prompt adalah hal yang mustahil karena:
1. Menghabiskan batas context window model.
2. Membengkakkan biaya tagihan API hingga jutaan token.
3. Menimbulkan degradasi penalaran (*Lost-in-the-Middle Problem*).

**Arsitektur Memori Berlapis OpenClaw (Dual-Memory Architecture)**:
1. **Short-Term Memory (Working Session Buffer)**:
   Menyimpan 10-20 interaksi pesan terakhir di basis data lokal (SQLite: `sessions.db`). Fokus pada konteks pembicaraan yang sedang berlangsung saat ini.
2. **Long-Term Memory (Vector Semantic Store)**:
   Mengekstrak fakta penting, preferensi pengguna, dan catatan permanen (misal: *"User menyukai kopi tanpa gula"*, *"Server staging beralamat di 10.0.1.5"*). Fakta ini diubah menjadi **Vector Embeddings** (koordinat numerik dalam ruang multi-dimensi) dan disimpan di vector store (Chroma / SQLite-vec). Saat pengguna bertanya tentang topik terkait di masa depan, OpenClaw melakukan pencarian semantik dan menyuntikkan fakta relevan ke dalam prompt.

## 4. Why?
- **Pengalaman Personal yang Nyata (True Personal Assistant)**: Anda tidak perlu memperkenalkan diri atau mengulang instruksi teknis berulang kali. Agen mengingat bahwa Anda menggunakan OS Windows, menyukai jawaban ringkas, dan memiliki alergi kacang.
- **Efisiensi Token Maksimal**: Hanya mengambil informasi masa lalu yang benar-benar relevan dengan pertanyaan saat ini ($K$ fakta teratas), menghemat 95% biaya token dibandingkan mengirim seluruh log chat.

## 5. What?
### Taksonomi Memori Agen AI:
1. **Working Memory (Konteks Sesi Aktif)**:
   - Disimpan di: SQLite table `chat_messages`.
   - Umur: Sesi obrolan saat ini (direset saat pengguna mengetik `/reset` atau setelah 24 jam tidak aktif).
2. **Semantic Memory (Pengetahuan Fakta & Konsep)**:
   - Disimpan di: Vector Database (ChromaDB / `sqlite-vec`).
   - Contoh: Aturan arsitektur perusahaan, dokumentasi API, preferensi bahasa.
3. **Episodic Memory (Pengalaman & Catatan Kejadian Masa Lalu)**:
   - Disimpan di: Vector Database dengan timestamp metadata.
   - Contoh: *"Pada 2 Maret 2026, deploy versi 1.2 gagal karena migrasi database error"*.

### Apa itu Vector Embedding?
Proses matematika yang mengubah teks bahasa manusia menjadi deretan angka (vektor) berdimensi tinggi (misal 1536 angka). Kalimat dengan makna serupa akan memiliki koordinat yang berdekatan dalam ruang vektor:
- $\vec{A}$: *"Saya ingin minum kopi"*
- $\vec{B}$: *"Di mana kedai espresso terdekat?"* $\rightarrow$ **Cosine Similarity: 0.89 (Sangat Dekat!)**
- $\vec{C}$: *"Harga saham teknologi anjlok"* $\rightarrow$ **Cosine Similarity: 0.12 (Jauh!)**

## 6. How?
### Alur Penyimpanan & Pemanggilan Memori:
```text
1. ALUR PENYIMPANAN (WRITE PATH):
[User Chat] ──> "Saya baru saja pindah rumah ke BSD City Tangerang"
                     │
                     ├── 1. Simpan ke SQLite (Short-term buffer)
                     │
                     ▼ 2. LLM Fact Extractor mengekstrak fakta permanen:
                          Fact: "Lokasi tempat tinggal pengguna: BSD City, Tangerang"
                     │
                     ▼ 3. Embedding Model (text-embedding-3-small)
                          Vektor: [0.012, -0.045, 0.088, ..., 0.031]
                     │
                     ▼ 4. Simpan ke [Local Vector Store (ChromaDB / SQLite-vec)]


2. ALUR PEMANGGILAN (RECALL PATH - 3 MINGGU KEMUDIAN):
[User Chat] ──> "Cuaca hari ini bagaimana ya?"
                     │
                     ├── 1. Generate Query Vector: Embedding("Cuaca hari ini")
                     │
                     ▼ 2. Cosine Similarity Search ke Vector Store:
                          Hasil Relevan: "Lokasi tempat tinggal pengguna: BSD City" (Score: 0.86)
                     │
                     ▼ 3. Context Injection ke Prompt:
                          System: "Gunakan data konteks berikut: Lokasi user: BSD City"
                     │
                     ▼ 4. Agen Menjalankan Tool Cuaca untuk "BSD City" & Membalas:
[User Chat] <── "Cuaca di BSD City hari ini cerah berawan dengan suhu 29°C."
```

## 7. Analogy
- **Short-Term Memory = Meja Kerja Anda Saat Ini**: Tumpukan 5 lembar kertas yang sedang Anda baca dan diskusikan menit ini. Meja ini dibersihkan setiap Anda selesai rapat.
- **Long-Term Memory = Lemari Arsip Ruang Kerja**: Ratusan map arsip rapi di lemari besi. Saat Anda membahas proyek A, asisten Anda membuka laci lemari, mengambil 1 lembar map arsip proyek A yang relevan, meletakkannya di atas meja kerja, lalu menyimpannya kembali ke lemari setelah selesai.

## 8. Diagram

```text
================ DUAL-MEMORY ARCHITECTURE OPENCLAW ================

                       [User Prompt Masuk]
                               │
       ┌───────────────────────┴───────────────────────┐
       ▼                                               ▼
[Short-Term Buffer]                         [Long-Term Vector Memory]
 (SQLite: sessions.db)                       (Embedding & Vector Search)
 - Ambil 5 chat terakhir                     - Query: Cosine Similarity
 - Menjaga koherensi dialog                  - Ambil Top-3 Fakta Relevan
       │                                               │
       └───────────────────────┬───────────────────────┘
                               │
                               ▼
                   [Augmented Prompt Context]
            (System Prompt + Memory Facts + History)
                               │
                               ▼
                          [LLM Engine]
```

## 9. Simple Example: Perhitungan Cosine Similarity
Rumus mengukur kemiripan dua vektor $\vec{A}$ dan $\vec{B}$:
$$\text{Similarity}(\vec{A}, \vec{B}) = \frac{\vec{A} \cdot \vec{B}}{\|\vec{A}\| \|\vec{B}\|}$$
Nilai berada di antara:
- `1.0`: Makna identik 100%.
- `0.0`: Tidak ada korelasi semantik sama sekali.
- `-1.0`: Makna berlawanan secara polar.
Ambarg batas (*threshold*) yang umum digunakan untuk menyaring fakta relevan adalah similarity $\ge 0.70$.

## 10. Practical Example: Konfigurasi Memory Store di `config.json`
```json
{
  "memory": {
    "shortTerm": {
      "type": "sqlite",
      "maxHistoryMessages": 10
    },
    "longTerm": {
      "type": "vector",
      "engine": "sqlite-vec",
      "embeddingProvider": "google-gemini",
      "embeddingModel": "text-embedding-004",
      "similarityThreshold": 0.72,
      "topK": 3
    }
  }
}
```

## 11. Real World Example
- **Automasi Asisten Dokter Pribadi**: Agen mengingat riwayat alergi obat pasien (*Amoksisilin*) dari percakapan 2 bulan lalu yang tersimpan di vector store. Ketika dokter mendiskusikan resep antibiotik hari ini, agen secara otomatis menyuntikkan peringatan: *"Peringatan: Pasien tercatat memiliki alergi terhadap antibiotik golongan penisilin!"*.

## 12. Trade-offs

| Parameter | SQLite Raw Text History | Vector Semantic Memory |
|---|---|---|
| **Kecepatan Query** | Ekstrem Cepat (B-Tree Index) | Cepat (HNSW / Approximate Nearest Neighbor) |
| **Kapasitas Penyimpanan**| Terbatas (Harus dipangkas) | Sangat Besar (Jutaan embedding fakta) |
| **Pola Pencarian** | Exact Match (`WHERE text LIKE %...%`) | **Semantic Meaning Search (Makna Serupa)** |
| **Biaya Ingestion** | Gratis (Nol komputasi AI) | Butuh 1x panggilan API embedding saat menyimpan |

## 13. When To Use Long-Term Memory
- Menyimpan fakta penting profil pengguna, preferensi gaya kerja, aturan proyek, dan dokumentasi yang sering diacu di masa depan.

## 14. When NOT To Use Long-Term Memory
- Percakapan santai sesaat yang tidak memiliki nilai jangka panjang (misal: *"Oke bro, makasih infonya"*). Menyimpan chat basa-basi ke vector store hanya akan mengotori database semantik (*Vector Noise Pollution*).

## 15. Common Mistakes
1. **Memasukkan Seluruh Transkrip Obrolan Mentah ke Vector Store**: Mem-vektorisasi baris *"halo"*, *"iya"*, *"ok"* akan menurunkan akurasi pencarian semantik. Gunakan modul ekstraktor fakta (*Fact Extraction LLM*) untuk menyaring hanya intisari informasi penting sebelum di-embed.
2. **Menggunakan Model Embedding yang Berbeda untuk Query dan Storage**: Menyimpan fakta menggunakan OpenAI `text-embedding-3-small` (1536 dimensi), tetapi mencari menggunakan Ollama (768 dimensi). Vektor dengan dimensi berbeda tidak dapat dihitung kesamaannya secara matematis!
3. **Threshold Kesamaan Terlalu Rendah**: Menyetel threshold 0.40 menyebabkan agen menyuntikkan fakta acak yang tidak relevan ke dalam prompt, membingungkan penalaran LLM (*Context Contamination*).

## 16. Best Practices
- **Auto-Eviction / Memory Consolidation**: Jalankan proses konsolidasi berkala di malam hari: gabungkan fakta-fakta serupa dan hapus fakta usang yang telah diperbarui (*Memory Garbage Collection*).
- **Metadata Tagging**: Beri label timestamp, kategori (preferensi, kredensial, proyek), dan tingkat privasi pada setiap entri vektor.
- **Penyimpanan Lokal (Zero Cloud)**: Gunakan library vektor in-process seperti `sqlite-vec` atau Chroma lokal agar embedding data pribadi tersimpan di harddisk Anda sendiri.

## 17. Troubleshooting
- **Masalah: Agen tidak mengingat fakta yang baru saja disampaikan pengguna kemarin**.
  - *Sebab*: Nilai cosine similarity berada di bawah ambang batas (misal skor 0.68 sedangkan threshold diatur 0.75), atau fakta belum sempat di-ingest ke vector store.
  - *Solusi*: Turunkan threshold menjadi 0.70 atau gunakan pencarian hybrid (*Hybrid Search: Vector + Full-Text BM25*).

## 18. Hands-on Practice
Mari kita buktikan implementasi nyata Dual-Memory System: penyimpanan SQLite working session dan mesin Vector Embedding sederhana dengan Cosine Similarity di `hands-on/m01/memory_systems_sim.js`.

## 19. Exercises & Challenge
- **Exercise**: Hitung Cosine Similarity antara dua vektor dimensi 3: $\vec{A} = [1, 0, 1]$ dan $\vec{B} = [0, 1, 1]$.  
  *(Perhitungan: Dot product $= (1 \times 0) + (0 \times 1) + (1 \times 1) = 1$. Magnitudo $\|\vec{A}\| = \sqrt{2}$, $\|\vec{B}\| = \sqrt{2}$. Similarity $= \frac{1}{\sqrt{2} \times \sqrt{2}} = \frac{1}{2} = 0.50$)*.
- **Challenge**: Rancang skema *Memory Conflict Resolution*: jika pengguna berkata *"Saya sekarang sudah pindah kerja ke Google"*, bagaimana sistem memperbarui memori lama yang mencatat *"User bekerja di Microsoft"*?

## 20. Summary
Sistem memori adalah pembeda utama antara chatbot mainan dan asisten AI sejati. Melalui perpaduan **Short-term Working Memory** untuk kelancaran dialog instan dan **Long-term Vector Memory** berbasis cosine similarity, OpenClaw mampu mengingat identitas, preferensi, dan pengetahuan Anda sepanjang waktu dengan efisiensi token yang optimal.
