# BAB 01 — Fondasi LLM, Tokenization, Transformers, & Prompt Engineering Patterns — Quiz & Chapter Challenge

---

## 📝 Bagian 1: Ujian Konsep & Pemahaman Teknis (10 Soal Pilihan Ganda)

---

### Soal 1

Seorang AI Engineer menganalisis output tokenizer GPT-2 untuk kalimat berikut:

```python
from transformers import GPT2Tokenizer

tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
tokens = tokenizer.encode("unhappiness")
print(tokens)
# Output: [403, 34, 11521, 1108]  ← (ilustrasi)
print(tokenizer.convert_ids_to_tokens(tokens))
# Output: ['un', 'h', 'app', 'iness']
```

Mengapa kata `"unhappiness"` dipecah menjadi 4 token alih-alih 1 token tunggal, dan apa implikasi langsungnya terhadap perhitungan `context window` suatu model?

**A.** Karena GPT-2 menggunakan character-level tokenization; setiap karakter dihitung sebagai 1 token, sehingga kalimat panjang akan selalu melebihi context window lebih cepat dibanding word-level tokenization.

**B.** Karena GPT-2 menggunakan Byte-Pair Encoding (BPE) yang membangun vocabulary berdasarkan frekuensi pasangan byte/karakter dalam corpus pelatihan; kata yang jarang muncul sebagai unit utuh akan dipecah menjadi subword yang lebih sering muncul, sehingga satu kata bisa mengonsumsi beberapa token dari batas context window.

**C.** Karena GPT-2 menggunakan WordPiece tokenization yang memaksimalkan kemungkinan likelihood dari vocabulary; pemecahan terjadi karena model tidak mengenali kata tersebut sama sekali dan menggantinya dengan token `[UNK]`.

**D.** Karena tokenizer mendeteksi morfologi bahasa Inggris secara linguistik (prefix `un-`, root `happy`, suffix `-ness`) dan memecahnya berdasarkan aturan grammar, yang menyebabkan overhead komputasi pada attention layer.

**✅ Kunci Jawaban: B**

**📖 Penjelasan Mendalam:**

**Mengapa B benar:** GPT-2 menggunakan **Byte-Pair Encoding (BPE)**, sebuah algoritma kompresi data yang diadaptasi untuk tokenisasi NLP. Proses pembangunan vocabulary BPE dimulai dari karakter individual, kemudian secara iteratif menggabungkan pasangan yang paling sering muncul bersama dalam corpus pelatihan. Kata `"unhappiness"` dipecah karena kombinasi karakter tersebut sebagai unit tunggal tidak cukup sering muncul dalam corpus pelatihan GPT-2 untuk mendapatkan slot vocabulary sendiri. Implikasi terhadap context window sangat signifikan: jika model memiliki context window 4096 token, sebuah dokumen yang mengandung banyak kata teknis/jarang (yang masing-masing dipecah menjadi 3-5 subword) akan "mengisi" context window jauh lebih cepat dibanding dokumen dengan kata-kata umum. Ini adalah pertimbangan kritis dalam merancang sistem RAG atau long-document processing.

**Mengapa A salah:** GPT-2 tidak menggunakan character-level tokenization. Character-level tokenizer memang menghasilkan lebih banyak token per kata, tetapi mekanismenya berbeda fundamental. BPE bekerja pada level subword, bukan karakter murni.

**Mengapa C salah:** WordPiece adalah tokenizer yang digunakan oleh BERT (bukan GPT-2), dan mekanismenya berbasis likelihood maximization. Lebih penting lagi, BPE tidak menghasilkan token `[UNK]` untuk kata yang tidak dikenal — ia justru memecah kata tersebut menjadi subword yang dikenal hingga ke level byte, sehingga secara teoritis dapat merepresentasikan karakter Unicode apapun.

**Mengapa D salah:** Tokenizer BPE tidak memiliki pengetahuan linguistik atau morfologis. Pemecahan sepenuhnya bersifat statistik berdasarkan frekuensi corpus. Fakta bahwa `"un"` dan `"ness"` adalah unit linguistik yang bermakna hanyalah korelasi kebetulan karena prefiks/sufiks memang sering muncul bersama kata lain dalam corpus.

---

### Soal 2

Perhatikan pseudocode implementasi **Scaled Dot-Product Attention** berikut:

```python
import torch
import torch.nn.functional as F
import math

def scaled_dot_product_attention(Q, K, V, mask=None):
    d_k = Q.size(-1)
    
    # Step 1
    scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(d_k)
    
    # Step 2
    if mask is not None:
        scores = scores.masked_fill(mask == 0, -1e9)
    
    # Step 3
    attn_weights = F.softmax(scores, dim=-1)
    
    # Step 4
    output = torch.matmul(attn_weights, V)
    return output, attn_weights
```

Seorang engineer menemukan bahwa tanpa faktor pembagi `math.sqrt(d_k)`, model menghasilkan loss yang tidak stabil dan gradient vanishing selama training. Apa penjelasan teknis yang paling akurat?

**A.** Tanpa `sqrt(d_k)`, hasil dot product menjadi terlalu kecil mendekati nol, menyebabkan softmax menghasilkan distribusi yang terlalu uniform dan model tidak bisa belajar pola attention yang spesifik.

**B.** Tanpa `sqrt(d_k)`, dot product antara Q dan K yang berdimensi tinggi akan menghasilkan nilai skalar yang sangat besar dalam magnitudo, mendorong softmax ke daerah saturasi di mana gradiennya mendekati nol, sehingga backpropagation menjadi tidak efektif.

**C.** Faktor `sqrt(d_k)` berfungsi sebagai regularisasi L2 pada attention weights untuk mencegah overfitting terhadap token tertentu, bukan untuk alasan numerik.

**D.** Tanpa `sqrt(d_k)`, operasi `masked_fill` dengan nilai `-1e9` akan menyebabkan numerical overflow karena nilai mask ditambahkan ke scores yang sudah sangat besar, menghasilkan nilai `inf` yang merusak komputasi.

**✅ Kunci Jawaban: B**

**📖 Penjelasan Mendalam:**

**Mengapa B benar:** Ini adalah analisis matematis yang dikemukakan dalam paper asli "Attention Is All You Need" (Vaswani et al., 2017). Jika komponen Q dan K diinisialisasi dari distribusi dengan mean 0 dan variance 1, maka dot product `Q·Kᵀ` untuk vektor berdimensi `d_k` akan memiliki variance sebesar `d_k`. Ketika `d_k` besar (misalnya 512 atau 1024), nilai dot product bisa sangat besar. Fungsi softmax `σ(x)ᵢ = exp(xᵢ) / Σexp(xⱼ)` bersifat sangat sensitif terhadap perbedaan nilai input ketika nilai-nilai tersebut besar: ia akan mendorong probabilitas hampir seluruhnya ke satu token (saturasi), menghasilkan gradient `∂softmax/∂x ≈ 0`. Ini adalah manifestasi dari **vanishing gradient problem** spesifik pada attention mechanism. Pembagian dengan `√d_k` menormalisasi variance kembali ke 1, menjaga softmax bekerja di daerah yang gradiensnya informatif.

**Mengapa A salah:** Ini adalah kebalikan dari yang terjadi. Tanpa scaling, nilai dot product menjadi **terlalu besar** (bukan terlalu kecil), bukan mendekati nol. Distribusi softmax yang terlalu uniform justru terjadi ketika nilai input softmax mendekati nol (semua sama), bukan ketika sangat besar.

**Mengapa C salah:** `sqrt(d_k)` sama sekali tidak berfungsi sebagai regularisasi L2. Regularisasi L2 bekerja pada parameter model (weights) dengan menambahkan penalti ke loss function. Scaling factor pada attention adalah murni motivasi numerik/statistik untuk stabilitas training.

**Mengapa D salah:** Meskipun `masked_fill(-1e9)` memang berinteraksi dengan scores, ini bukan alasan utama mengapa scaling diperlukan. Bahkan dengan mask, jika scores yang tidak di-mask sudah sangat besar, masalah saturasi softmax tetap terjadi. Nilai `-1e9` dirancang justru untuk membuat token yang di-mask mendekati probabilitas nol setelah softmax, dan ini bekerja dengan baik terlepas dari scaling.

---

### Soal 3

Sebuah tim AI Engineer membandingkan dua pendekatan prompting untuk tugas klasifikasi sentimen pada sistem produksi:

```
# Pendekatan Alpha — Zero-Shot
prompt_alpha = """
Klasifikasikan sentimen teks berikut sebagai POSITIF, NEGATIF, atau NETRAL.
Teks: "{input_text}"
Sentimen:"""

# Pendekatan Beta — Few-Shot
prompt_beta = """
Klasifikasikan sentimen teks berikut sebagai POSITIF, NEGATIF, atau NETRAL.

Contoh:
Teks: "Produk ini luar biasa, saya sangat puas!"
Sentimen: POSITIF

Teks: "Pengiriman lambat dan barang rusak."
Sentimen: NEGATIF

Teks: "Barang sudah diterima."
Sentimen: NETRAL

Teks: "{input_text}"
Sentimen:"""
```

Dalam eksperimen A/B test dengan 1000 sampel teks domain spesifik (ulasan produk elektronik teknis), Pendekatan Beta menunjukkan akurasi 23% lebih tinggi. Namun seorang engineer mengusulkan untuk tidak menggunakan few-shot karena "membuang token". Apa counter-argument teknis yang paling tepat?

**A.** Engineer tersebut benar; few-shot prompting selalu lebih mahal dan seharusnya digantikan dengan fine-tuning model untuk domain spesifik, yang lebih hemat token dalam jangka panjang.

**B.** Few-shot examples berfungsi sebagai **in-context learning** yang secara efektif mengkondisikan distribusi output model tanpa mengubah parameter; biaya token tambahan dapat dijustifikasi dengan menghitung trade-off antara cost per token vs. cost of misclassification, dan untuk domain spesifik, few-shot seringkali lebih cost-effective dibanding fine-tuning yang memerlukan data berlabel, infrastruktur training, dan deployment model terpisah.

**C.** Few-shot prompting mengubah bobot internal model secara sementara selama inferensi melalui mekanisme gradient descent mini yang terjadi di dalam attention layers, sehingga akurasi yang lebih tinggi bukan dari contoh teks melainkan dari adaptasi parameter real-time.

**D.** Perbedaan akurasi 23% tidak signifikan secara statistik untuk 1000 sampel dan kemungkinan merupakan overfitting terhadap distribusi test set; zero-shot lebih robust untuk produksi.

**✅ Kunci Jawaban: B**

**📖 Penjelasan Mendalam:**

**Mengapa B benar:** Ini mencakup beberapa konsep kritis. Pertama, **in-context learning (ICL)** adalah fenomena yang telah dibuktikan secara empiris di mana LLM dapat mengadaptasi perilakunya berdasarkan contoh dalam prompt tanpa modifikasi parameter — ini adalah property emergent dari pre-training skala besar. Kedua, argumen "membuang token" harus dievaluasi secara bisnis: jika misklasifikasi sentimen menyebabkan kerugian (misalnya, customer complaint yang tidak tertangani), maka biaya token tambahan untuk few-shot jauh lebih kecil. Ketiga, alternatif fine-tuning memerlukan: (a) dataset berlabel berkualitas tinggi, (b) infrastruktur GPU untuk training, (c) pipeline deployment model baru, (d) monitoring drift — semua ini memiliki biaya yang jauh lebih besar dari beberapa ratus token per request.

**Mengapa A salah:** Pernyataan "few-shot selalu lebih mahal dari fine-tuning dalam jangka panjang" adalah oversimplifikasi yang salah. Fine-tuning memerlukan biaya upfront yang sangat besar (data labeling, compute training, deployment), sementara few-shot hanya menambah token per request. Untuk volume request yang tidak ekstrem besar, few-shot bisa jauh lebih ekonomis. Selain itu, "always" adalah klaim absolut yang tidak valid dalam engineering.

**Mengapa C salah:** Ini adalah miskonsepsi fundamental tentang cara kerja LLM selama inferensi. Tidak ada gradient descent yang terjadi saat inferensi standar — bobot model adalah frozen (tidak berubah). In-context learning bekerja murni melalui forward pass, di mana contoh dalam prompt mempengaruhi attention patterns dan distribusi output token berikutnya. Beberapa penelitian teoritis menghipotesiskan bahwa ICL "mensimulasikan" gradient descent implisit, tetapi ini adalah interpretasi mekanistik, bukan proses komputasi aktual.

**Mengapa D salah:** Dengan 1000 sampel, perbedaan 23% akurasi (230 sampel) sangat signifikan secara statistik (confidence interval akan sangat sempit). Argumen "overfitting terhadap test set" hanya valid jika few-shot examples dipilih secara tidak independen dari test set, yang tidak disebutkan dalam skenario. Ini adalah argumen yang tidak berdasar tanpa bukti metodologi yang buruk.

---

### Soal 4

Perhatikan arsitektur Transformer berikut dan pertanyaan tentang **Positional Encoding**:

```python
import torch
import math

class PositionalEncoding(nn.Module):
    def __init__(self, d_model, max_seq_len=5000, dropout=0.1):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        
        # Buat matrix PE
        pe = torch.zeros(max_seq_len, d_model)
        position = torch.arange(0, max_seq_len).unsqueeze(1).float()
        
        div_term = torch.exp(
            torch.arange(0, d_model, 2).float() * 
            (-math.log(10000.0) / d_model)
        )
        
        pe[:, 0::2] = torch.sin(position * div_term)  # dimensi genap
        pe[:, 1::2
