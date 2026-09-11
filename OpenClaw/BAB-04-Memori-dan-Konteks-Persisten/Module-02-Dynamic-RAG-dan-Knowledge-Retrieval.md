# Module 02: Dynamic RAG & Knowledge Retrieval untuk Personal Agent

## 1. Learning Objective
Setelah menyelesaikan modul ini, Anda akan mampu:
- Membangun pipeline **Retrieval-Augmented Generation (RAG)** mandiri untuk personal knowledge base agen OpenClaw.
- Menerapkan strategi **Document Chunking** yang optimal (ukuran chunk dan overlap) pada berkas Markdown, PDF, dan catatan harian.
- Menggabungkan kekuatan pencarian: **Dense Vector Semantic Search** dan **Sparse Keyword Search (BM25)** dalam arsitektur **Hybrid Search**.
- Menerapkan **Re-ranking** untuk memastikan hanya potongan dokumen paling relevan yang disuntikkan ke dalam prompt LLM.

## 2. Prerequisite
- Memahami konsep Vector Embeddings dan Cosine Similarity dari Module 01.
- Pemahaman dasar tentang parsing berkas teks/markdown.

## 3. Concept
Sebagai seorang developer atau profesional, Anda memiliki ratusan berkas catatan pribadi: catatan proyek di Obsidian, cheatsheet sintaks di Markdown, SOP deployment server, hingga buku panduan PDF.

Memberikan seluruh folder dokumen Anda ke LLM setiap kali bertanya adalah hal yang mustahil.  
**Dynamic RAG (Retrieval-Augmented Generation)** adalah teknik yang memungkinkan agen AI Anda:
1. Membaca dan memecah (*chunking*) seluruh dokumen catatan Anda di latar belakang.
2. Mengubah setiap potongan menjadi vektor dan mengindeks kata kuncinya.
3. Saat Anda bertanya melalui Telegram/WhatsApp (misal: *"Bagaimana SOP restart database kluster kita?"*), agen secara dinamis mencari 2-3 potongan dokumen yang paling relevan dari harddisk Anda, membacanya, dan menyajikan jawaban yang akurat dan berbasis fakta (*grounded in truth*).

## 4. Why?
- **Mencegah Halusinasi LLM**: Model AI tidak lagi mengarang prosedur teknis; jawabannya berpatokan 100% pada berkas dokumentasi internal yang Anda miliki.
- **Pencarian Kilat**: Menemukan informasi spesifik di ribuan baris catatan proyek dalam waktu < 200 milidetik langsung dari ponsel.
- **Pembaruan Instan**: Anda cukup menambahkan file `.md` baru ke folder `~/.openclaw/knowledge/`, dan agen seketika menguasai pengetahuan baru tersebut tanpa perlu fine-tuning model yang mahal.

## 5. What?
### Komponen Pipeline Dynamic RAG:
1. **Document Loader & Preprocessor**:
   Membaca format file `.md`, `.txt`, `.pdf`, `.json` dari direktori knowledge base.
2. **Text Chunker (Pemotong Teks)**:
   - *Chunk Size*: 500 - 1000 karakter per bagian.
   - *Chunk Overlap*: 100 - 150 karakter (agar makna di perbatasan kalimat tidak terpotong).
3. **Hybrid Indexing Engine**:
   - *Dense Retrieval*: Menggunakan Vector Embeddings untuk menangkap makna konseptual (*"cara mengatasi server hang"*).
   - *Sparse Retrieval (BM25)*: Menggunakan indeks kata kunci presisi untuk mencocokkan kode error eksak (*"ERR_CONN_REFUSED_504"*, nomor seri, atau nama fungsi `sanitizeInput()`).
4. **Re-ranker & Context Injector**:
   Mengurutkan kembali hasil pencarian hybrid dan menyaring dokumen yang memiliki tingkat relevansi tertinggi ke dalam prompt sistem agen.

## 6. How?
### Alur Pemrosesan Dokumen RAG:
```text
FASE 1: INGESTION PIPELINE (Offline / Background)
[Folder Dokumen: ~/notes/] 
         │
         ▼ 1. Baca Berkas Markdown / PDF
[Text Chunking Engine] (Ukuran: 600 chars, Overlap: 100 chars)
         │
         ├──> 2a. Ekstrak Indeks Kata Kunci ──> [BM25 Inverted Index]
         │
         └──> 2b. Generate Embeddings       ──> [Vector Store (Chroma/SQLite-vec)]


FASE 2: DYNAMIC RETRIEVAL & QUERY (Saat User Bertanya)
[User Chat di WhatsApp] ──> "Bagaimana cara rollback migrasi database Django?"
                                    │
         ┌──────────────────────────┴──────────────────────────┐
         ▼                                                     ▼
[Dense Vector Search]                                 [BM25 Keyword Search]
(Mencari makna: pemulihan database)                   (Mencari kata: 'rollback', 'Django')
         │                                                     │
         └──────────────────────────┬──────────────────────────┘
                                    │
                                    ▼
                 [Hybrid Fusion Score & Re-Ranker]
                                    │
                                    ▼ (Ambil Top-2 Potongan Terbaik)
                 [Suntikkan Potongan ke Prompt LLM]
                                    │
                                    ▼
[User Chat di WhatsApp] <── "Berdasarkan SOP di berkas 'devops-sop.md', jalankan: ..."
```

## 7. Analogy
- **LLM Murni Tanpa RAG = Ujian Tutup Buku**: Siswa mengandalkan ingatan hafalan di kepalanya. Jika lupa atau ragu, siswa bisa mengarang jawaban yang terdengar meyakinkan tetapi salah (halusinasi).
- **LLM dengan RAG = Ujian Buka Buku dengan Asisten Cerdas**: Siswa diperbolehkan membuka perpustakaan buku pribadi. Saat melihat soal nomor 4, asisten membukakan halaman 42 buku SOP yang relevan dan meletakkannya di hadapan siswa. Siswa membaca halaman tersebut dan menulis jawaban yang 100% tepat.

## 8. Diagram

```text
================ DENSE VS SPARSE HYBRID RETRIEVAL ================

Pertanyaan User: "Error kode 0x882F saat deploy"

1. Dense Vector Search:
   - Memahami konsep umum: "Ada kegagalan deployment software".
   - Tetapi seringkali TIDAK BISA membedakan antara "0x882F" dan "0x883A" karena angka heksadesimal memiliki representasi embedding yang hampir serupa!

2. Sparse BM25 Keyword Search:
   - Mencocokkan string presisi eksak: "0x882F".

3. Solusi Hybrid:
   Dense Score (0.4) + BM25 Score (0.6) = 1.0 (Akurasi Sempurna!)
```

## 9. Simple Example: Algoritma Recursive Text Chunking
```javascript
function chunkText(text, chunkSize = 500, overlap = 100) {
  const chunks = [];
  let startIndex = 0;
  
  while (startIndex < text.length) {
    let endIndex = startIndex + chunkSize;
    chunks.push(text.substring(startIndex, endIndex));
    startIndex += (chunkSize - overlap); // Geser maju dengan overlap
  }
  return chunks;
}
```

## 10. Practical Example: Mengindeks Obsidian Vault Pribadi
Banyak developer mengelola catatan kerja di aplikasi **Obsidian** (kumpulan file `.md` lokal).
Anda cukup mengarahkan konfigurasi OpenClaw ke folder vault Anda:
```json
{
  "rag": {
    "knowledgePaths": ["/Users/budi/Documents/ObsidianVault/Engineering"],
    "watchForChanges": true,
    "chunkSize": 600,
    "chunkOverlap": 100
  }
}
```
Setiap kali Anda mengedit file catatan di Obsidian di laptop, daemon OpenClaw otomatis mendeteksi perubahan (*file watcher*), memperbarui indeks vektor lokal, dan agen Anda langsung memahami SOP terbaru!

## 11. Real World Example
- **Customer Support Agent untuk Dokumentasi Produk**: Perusahaan SaaS mengarahkan OpenClaw ke seluruh repositori dokumentasi Markdown mereka (500 artikel panduan). Ketika pelanggan mengirim chat di Telegram menanyakan cara integrasi webhook, agen menarik 3 bab dokumentasi yang relevan dan menyusun panduan langkah-demi-langkah yang akurat tanpa mengarang API fiktif.

## 12. Trade-offs

| Metode Retrieval | Kelebihan | Kekurangan |
|---|---|---|
| **Dense Vector Only** | Sangat baik memahami konsep abstrak, sinonim kata | Buruk dalam mencocokkan kata kunci unik (kode error, nama variabel) |
| **BM25 Keyword Only** | Sangat presisi pada nama kode, ID, dan istilah eksak | Gagal jika pengguna menggunakan sinonim kata yang berbeda |
| **Hybrid Search (Vector + BM25)**| **Kombinasi Terbaik (Konseptual + Eksak)** | Butuh 2 jenis indeks (Sedikit tambahan memori) |

## 13. When To Use
- Agen yang ditugaskan membaca dan menjawab berdasarkan berkas SOP, dokumentasi arsitektur, catatan proyek, atau buku panduan teknis.

## 14. When NOT To Use RAG
- Pertanyaan logika penalaran murni (seperti *"Tulis fungsi sorting binary search dalam bahasa Go"*) yang tidak bergantung pada dokumen privat Anda.

## 15. Common Mistakes
1. **Ukuran Chunk Terlalu Besar (> 3.000 karakter)**: Potongan yang terlalu besar memasukkan banyak informasi yang tidak relevan, mengencerkan fokus embedding (*Diluted Embedding Signal*).
2. **Ukuran Chunk Terlalu Kecil (< 100 karakter)**: Potongan kehilangan konteks kalimat utuh (misal hanya memuat satu baris *"Gunakan port 8080"*, tanpa tahu service apa yang menggunakan port tersebut).
3. **Mengabaikan Chunk Overlap**: Memotong teks tepat di tengah-tengah penjelasan parameter kritis, sehingga bagian penting terbelah menjadi dua potongan terpisah yang kehilangan maknanya.

## 16. Best Practices
- **Gunakan Chunk Overlap 15-20%**: Jika chunk berukuran 600 karakter, gunakan overlap 100-120 karakter.
- **Sertakan Metadata File**: Simpan nama berkas dan heading section (`# Arsitektur Database`) di setiap chunk metadata agar LLM dapat mengutip sumbernya: *"Berdasarkan berkas SOP-Database.md bagian Migrasi..."*.
- **Filter Berdasarkan Relevansi Skor**: Jangan suntikkan chunk ke prompt jika skor kesamaan berada di bawah ambang batas (misal < 0.65).

## 17. Troubleshooting
- **Masalah: Agen memberikan jawaban yang tidak sesuai dengan dokumen terbaru**.
  - *Sebab*: Berkas lama belum di-reindex setelah diedit di harddisk.
  - *Solusi*: Jalankan perintah sinkronisasi manual: `openclaw rag reindex --all`.

## 18. Hands-on Practice
Mari kita buktikan implementasi nyata pipeline Dynamic RAG: membaca dokumen markdown, memecah dengan overlap, melakukan Hybrid Search (Vector + Keyword), dan menginjeksi konteks ke jawaban agen di `hands-on/m02/personal_rag_engine.js`.

## 19. Exercises & Challenge
- **Exercise**: Jika sebuah dokumen memiliki panjang 2.500 karakter, dipecah dengan chunk size 1.000 karakter dan overlap 200 karakter. Berapa banyak potongan chunk yang akan dihasilkan?  
  *(Perhitungan: Chunk 1: 0-1000, Chunk 2: 800-1800, Chunk 3: 1600-2500 $\rightarrow$ Total 3 Chunks)*.
- **Challenge**: Rancang modul *Self-Correction RAG*: jika chunk dokumen yang ditarik tidak mengandung informasi yang cukup untuk menjawab pertanyaan pengguna, agen harus secara jujur menjawab *"Dokumen saya tidak memuat info ini"* alih-alih berhalusinasi.

## 20. Summary
Dynamic RAG adalah jembatan yang menghubungkan kecerdasan generatif LLM dengan kebenaran faktual berkas pribadi Anda. Melalui strategi **Chunking berbobot**, **Hybrid Search (Vector + BM25)**, dan **Context Injection**, OpenClaw menjadi asisten cerdas yang berwawasan luas, akurat, dan dapat dipercaya seutuhnya.
