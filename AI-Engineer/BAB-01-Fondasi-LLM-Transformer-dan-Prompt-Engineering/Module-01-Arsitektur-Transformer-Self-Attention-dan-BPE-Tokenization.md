# Arsitektur Transformer, Scaled Dot-Product Attention, Positional Encoding, & BPE Tokenization

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, Anda mampu:

1. **Menjelaskan** arsitektur Transformer end-to-end beserta peran setiap komponen (Encoder, Decoder, Multi-Head Attention, FFN, Layer Norm).
2. **Menghitung secara manual** output Scaled Dot-Product Attention dari matriks Q, K, V berukuran kecil dengan benar, termasuk langkah scaling dan masking.
3. **Mengimplementasikan** Positional Encoding sinusoidal dari nol menggunakan NumPy dan memverifikasi properti matematisnya.
4. **Membangun** tokenizer BPE sederhana dari corpus mentah, menjelaskan setiap iterasi merge, dan mendiagnosis kegagalan tokenisasi pada teks domain-spesifik.
5. **Mendiagnosis** bottleneck performa pada pipeline inference Transformer (attention complexity, sequence length, vocabulary size) dan merekomendasikan solusi konkret.
6. **Membandingkan** trade-off antara arsitektur Encoder-Only, Decoder-Only, dan Encoder-Decoder untuk use case production nyata.

---

## 2. Prerequisite

Sebelum melanjutkan, pastikan Anda telah memahami konsep berikut:

| Konsep | Level | Mengapa Diperlukan |
|---|---|---|
| **Linear Algebra** | Menengah | Operasi matriks (perkalian, transpose, dot product) adalah inti Attention |
| **Kalkulus Dasar** | Dasar | Memahami gradient flow dan mengapa softmax digunakan |
| **Python & NumPy** | Menengah | Semua implementasi menggunakan NumPy/PyTorch |
| **Neural Network Dasar** | Dasar | Memahami layer, activation function, backpropagation |
| **Konsep Embedding** | Dasar | Token harus dipahami sebagai vektor di ruang berdimensi tinggi |
| **Probabilitas & Softmax** | Dasar | Attention weight adalah distribusi probabilitas |

> **Cek Cepat:** Jika Anda dapat menghitung `np.matmul(A, B.T)` dan menjelaskan mengapa hasilnya berbeda dari `np.matmul(B.T, A)`, Anda siap melanjutkan.

---

## 3. Concept

### 3.1 Gambaran Besar: Apa Itu Transformer?

Transformer adalah arsitektur neural network yang diperkenalkan oleh Vaswani et al. pada paper *"Attention Is All You Need"* (Google Brain, 2017). Transformer **menghapus ketergantungan pada recurrence (RNN/LSTM)** dan **convolution**, menggantinya sepenuhnya dengan mekanisme **Self-Attention**.

Implikasinya revolusioner:
- Komputasi dapat **diparalelkan penuh** (tidak ada sequential dependency antar token)
- Model dapat mempelajari **dependensi jarak jauh** dalam satu langkah, bukan secara bertahap
- Scaling ke miliaran parameter menjadi feasible secara komputasi

### 3.2 Empat Pilar Utama

Modul ini mencakup empat konsep yang saling terkait erat:

```
┌─────────────────────────────────────────────────────────┐
│                    TRANSFORMER PIPELINE                  │
│                                                          │
│  Teks Mentah → [BPE Tokenization] → Token IDs           │
│       ↓                                                  │
│  Token IDs → [Token Embedding + Positional Encoding]     │
│       ↓                                                  │
│  Vektor → [Scaled Dot-Product Attention] → Context       │
│       ↓                                                  │
│  Context → [Transformer Architecture] → Output           │
└─────────────────────────────────────────────────────────┘
```

### 3.3 Mengapa Self-Attention Lebih Unggul dari RNN?

**RNN (masalah lama):**
- Memproses token **secara sekuensial**: token ke-100 bergantung pada token ke-99, yang bergantung pada ke-98, dst.
- Gradien **vanish atau explode** saat backpropagation melewati ratusan langkah
- Tidak bisa diparalelkan → lambat di GPU modern

**Self-Attention (solusi Transformer):**
- Setiap token **langsung "melihat" semua token lain** dalam satu operasi matriks
- Jarak antara dua token selalu **1 langkah** dalam graph komputasi
- Seluruh sequence diproses **secara paralel**

---

## 4. Why?

### 4.1 Masalah yang Dipecahkan

**Problem 1: Long-range dependency**

Bayangkan kalimat: *"The animal didn't cross the street because **it** was too tired."*

Kata "it" merujuk ke "animal" (bukan "street"). Dalam RNN, untuk memahami "it", model harus mempertahankan informasi "animal" melalui 6 hidden state perantara. Informasi ini sering hilang (vanishing gradient).

Dengan Self-Attention, "it" langsung menghitung korelasinya dengan **semua** kata lain dalam satu langkah.

**Problem 2: Sequential computation bottleneck**

RNN dengan sequence length 512 membutuhkan 512 langkah komputasi berurutan. Transformer membutuhkan **1 langkah** (satu operasi matriks besar yang diparalelkan di GPU).

**Problem 3: Representasi kontekstual yang kaku**

Word2Vec dan GloVe menghasilkan embedding **statis**: kata "bank" selalu punya vektor yang sama, baik dalam konteks "bank sungai" maupun "bank keuangan". Self-Attention menghasilkan representasi **kontekstual dinamis**: embedding berubah berdasarkan kata-kata di sekitarnya.

**Problem 4: Tokenisasi yang efisien untuk vocabulary terbuka**

Kata baru ("ChatGPT", "COVID-19") tidak ada dalam vocabulary fixed. BPE memecah kata menjadi sub-unit yang sudah dikenal, sehingga model bisa menangani kata apapun tanpa `<UNK>` token.

### 4.2 Dampak Bisnis

| Masalah Sebelumnya | Solusi Transformer | Dampak |
|---|---|---|
| Terjemahan mesin kaku | Encoder-Decoder Attention | Google Translate akurasi +55% |
| Chatbot tidak memahami konteks | Self-Attention | GPT-4, Claude, Gemini |
| Search engine keyword-based | BERT embedding | Google Search semantic understanding |
| Kode autocomplete lambat | Decoder-only Transformer | GitHub Copilot |

---

## 5. What?

### 5.1 Definisi Komponen

#### Transformer
> Arsitektur neural network berbasis mekanisme attention yang memproses sequence data secara paralel menggunakan representasi Query-Key-Value untuk menghitung relevansi antar elemen sequence.

**Spesifikasi teknis (Transformer original, Vaswani 2017):**
- `d_model = 512` (dimensi embedding)
- `N = 6` (jumlah layer encoder dan decoder)
- `h = 8` (jumlah attention heads)
- `d_ff = 2048` (dimensi feed-forward network)
- `d_k = d_v = d_model / h = 64`

#### Scaled Dot-Product Attention
> Fungsi attention yang menghitung weighted sum dari Value vectors, di mana bobotnya ditentukan oleh kompatibilitas antara Query dan Key vectors, dengan scaling faktor `1/√d_k`.

**Formula matematika:**

$$\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V$$

#### Multi-Head Attention
> Eksekusi Scaled Dot-Product Attention secara paralel sebanyak `h` kali dengan proyeksi linear yang berbeda, memungkinkan model fokus pada berbagai aspek informasi secara simultan.

**Formula:**

$$\text{MultiHead}(Q, K, V) = \text{Concat}(\text{head}_1, ..., \text{head}_h)W^O$$

$$\text{head}_i = \text{Attention}(QW_i^Q, KW_i^K, VW_i^V)$$

#### Positional Encoding
> Representasi vektor yang ditambahkan ke token embedding untuk menyuntikkan informasi posisi token dalam sequence, karena Self-Attention sendiri bersifat **permutation-invariant**.

**Formula sinusoidal:**

$$PE_{(pos, 2i)} = \sin\left(\frac{pos}{10000^{2i/d_{model}}}\right)$$

$$PE_{(pos, 2i+1)} = \cos\left(\frac{pos}{10000^{2i/d_{model}}}\right)$$

#### BPE (Byte Pair Encoding)
> Algoritma kompresi data yang diadaptasi untuk tokenisasi: secara iteratif menggabungkan pasangan karakter/sub-kata yang paling sering muncul dalam corpus, membangun vocabulary dari unit terkecil (karakter) hingga kata penuh.

---

## 6. How?

### 6.1 Scaled Dot-Product Attention: Step-by-Step

Misalkan input sequence: `["Kucing", "makan", "ikan"]`

Setelah embedding, setiap token direpresentasikan sebagai vektor. Untuk simplifikasi, gunakan `d_model = 4`, `d_k = 4`.

**Step 1: Buat matriks Q, K, V**

Setiap token embedding dikalikan dengan tiga matriks bobot yang dipelajari:
- `W_Q` (bobot Query): menghasilkan "apa yang saya cari?"
- `W_K` (bobot Key): menghasilkan "apa yang saya tawarkan?"
- `W_V` (bobot Value): menghasilkan "informasi apa yang saya bawa?"

```
Token Embeddings X (3 token, d_model=4):
X = [[1.0, 0.5, 0.2, 0.8],   ← "Kucing"
     [0.3, 1.0, 0.7, 0.1],   ← "makan"
     [0.9, 0.2, 1.0, 0.4]]   ← "ikan"

Q = X @ W_Q  → shape (3, d_k)
K = X @ W_K  → shape (3, d_k)
V = X @ W_V  → shape (3, d_v)
```

**Step 2: Hitung Raw Attention Scores**

```
Scores = Q @ K.T  → shape (3, 3)

Scores[i][j] = seberapa relevan token j untuk token i
               (dot product antara query token-i dan key token-j)
```

**Step 3: Scale**

```
Scaled_Scores = Scores / sqrt(d_k) = Scores / sqrt(4) = Scores / 2.0
```

**Mengapa dibagi `√d_k`?**

Tanpa scaling, jika `d_k` besar (misal 512), dot product menghasilkan nilai sangat besar. Softmax dari nilai sangat besar menghasilkan distribusi yang hampir one-hot (gradien mendekati nol → vanishing gradient). Scaling menjaga dot product dalam rentang yang wajar.

**Step 4: Masking (untuk Decoder)**

Pada Decoder, token ke-i tidak boleh "melihat" token ke-(i+1) dan seterusnya (autoregressive generation). Tambahkan mask `-inf` pada posisi yang dilarang:

```
Mask = [[0,   -inf, -inf],
        [0,    0,   -inf],
        [0,    0,    0  ]]

Masked_Scores = Scaled_Scores + Mask
```

**Step 5: Softmax**

```
Attention_Weights = softmax(Masked_Scores, dim=-1)
→ Setiap baris menjadi distribusi probabilitas yang sum=1
```

**Step 6: Weighted Sum of Values**

```
Output = Attention_Weights @ V  → shape (3, d_v)

Output[i] = Σ_j (Attention_Weights[i][j] * V[j])
           = representasi kontekstual token-i
```

---

### 6.2 Multi-Head Attention: Step-by-Step

```
Step 1: Project Q, K, V ke h subspace berbeda
        head_i = Attention(Q @ W_i^Q, K @ W_i^K, V @ W_i^V)
        
Step 2: Jalankan Attention di setiap head secara paralel
        head_1: fokus pada hubungan sintaksis
        head_2: fokus pada hubungan semantik
        head_3: fokus pada posisi relatif
        ... dst

Step 3: Concatenate semua head output
        MultiHead_output = Concat(head_1, ..., head_h)
        shape: (seq_len, h * d_v) = (seq_len, d_model)

Step 4: Project kembali ke d_model
        Output = MultiHead_output @ W^O
```

**Intuisi:** Setiap head belajar "aspek" perhatian yang berbeda. Head 1 mungkin belajar subject-verb agreement, head 2 belajar coreference resolution, head 3 belajar temporal relations, dst.

---

### 6.3 Arsitektur Transformer Lengkap: Step-by-Step

**Encoder (untuk setiap layer dari N=6):**

```
Input → Token Embedding + Positional Encoding
      ↓
[Layer 1]
  → Multi-Head Self-Attention(Q=X, K=X, V=X)
  → Add & LayerNorm (residual connection)
  → Feed-Forward Network (Linear → ReLU → Linear)
  → Add & LayerNorm
      ↓
[Layer 2...N] (sama)
      ↓
Encoder Output (contextual representations)
```

**Decoder (untuk setiap layer dari N=6):**

```
Target → Token Embedding + Positional Encoding
       ↓
[Layer 1]
  → Masked Multi-Head Self-Attention (causal mask)
  → Add & LayerNorm
  → Multi-Head Cross-Attention(Q=decoder, K=encoder_out, V=encoder_out)
  → Add & LayerNorm
  → Feed-Forward Network
  → Add & LayerNorm
       ↓
[Layer 2...N] (sama)
       ↓
Linear → Softmax → Probability distribution over vocabulary
```

**Feed-Forward Network (FFN):**

```
FFN(x) = max(0, x @ W_1 + b_1) @ W_2 + b_2

W_1: (d_model
