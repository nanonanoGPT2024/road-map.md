# Bab 06: Natural Language Processing & Large Language Models
## Modul 01: Foundations of Modern NLP: Tokenization Subword, Vector Embeddings, dan Mekanisme Multi-Head Attention

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Mengonstruksi Subword Tokenizer Deterministik**: Menganalisis dan membangun algoritma *Byte-Pair Encoding* (BPE) dari tingkat byte primitif, menangani kasus *Out-of-Vocabulary* (OOV), serta mencegah *tokenization leakage* lintas partisi data.
2. **Memformulasi Matematika Self-Attention**: Menurunkan secara matematis dan mengimplementasikan mekanisme *Scaled Dot-Product Attention* serta *Multi-Head Attention* (MHA) berkinerja tinggi menggunakan operasi tensor PyTorch berorientasi efisiensi memori.
3. **Menerapkan Skema Positional Representation**: Mengintegrasikan *Sinusoidal Positional Encoding* absolut dan mengevaluasi transisinya ke *Rotary Position Embedding* (RoPE) untuk mengkodekan informasi temporal/urutan sekuens secara akurat.
4. **Membangun Arsitektur Transformer Block Pre-LN**: Mengembangkan blok *Transformer Encoder/Decoder* standar industri dengan arsitektur *Pre-Layer Normalization* (Pre-LN), residual skip connections, dan feed-forward networks (FFN) berbasis aktivasi modern.
5. **Mendiagnosis Karakteristik Komputasi $O(N^2)$**: Mengidentifikasi titik kritis konsumsi memori dan latensi akibat kompleksitas kuadratik pada sequence length $N$, serta merancang strategi padding dan causal masking yang deterministik.

---

### 2. Concept Overview

Pemrosesan Bahasa Alami (*Natural Language Processing* / NLP) modern bertumpu pada pergeseran paradigma dari representasi simbolik diskrit (aturan gramatikal, n-gram, *Bag-of-Words*) menuju representasi geometris kontinu berdimensi tinggi (*continuous dense vector representations*). 

#### Mental Model: Dari Simbol Menuju Topologi Vektor
Bahasa manusia bersifat diskrit, komposisional, dan sarat ambiguitas kontekstual. Komputer tidak dapat memproses string secara langsung tanpa memetakannya ke dalam ruang numerik. 
1. **Tokenisasi**: Memecah aliran teks mentah menjadi fragmen subword terkecil yang optimal secara komputasi, menyeimbangkan ukuran kosakata (*vocabulary size*) dengan panjang sekuens (*sequence length*).
2. **Embedding**: Memproyeksikan token diskrit ke dalam *manifold* berdimensi tinggi ($\mathbb{R}^{d_{model}}$), di mana jarak euklidian dan *cosine similarity* mencerminkan kedekatan semantik dan sintaktis.
3. **Mekanisme Attention**: Menghilangkan batasan arsitektur rekuren (RNN/LSTM) yang memproses data secara sekuensial langkah-demi-langkah. Self-Attention memungkinkan setiap token dalam sekuens berinteraksi secara langsung dengan seluruh token lainnya dalam satu langkah komputasi paralel, menghitung distribusi bobot dinamis berdasarkan relevansi kontekstual.

```
[Teks Mentah] 
      │
      ▼ (Subword Tokenization - BPE/WordPiece)
[Token IDs: Integers] 
      │
      ▼ (Token Lookup Matrix + Positional Encoding)
[Dense Vectors: X ∈ ℝ^(B × N × d_model)]
      │
      ▼ (Proyeksi Linear ke Query, Key, Value)
[Q, K, V Tensor]
      │
      ▼ (Scaled Dot-Product Attention Engine)
[Context-Aware Representations ∈ ℝ^(B × N × d_model)]
```

---

### 3. Why It Matters

Dalam lanskap komputasi enterprise modern, pemahaman mekanistik atas fondasi Transformer bukan sekadar kebutuhan teoritis, melainkan prasyarat rekayasa untuk mengatasi tantangan operasional berikut:

* **Eliminasi Bottleneck Sekuensial**: RNN dan LSTM memiliki ketergantungan temporal $h_t = f(h_{t-1}, x_t)$ yang memblokir paralelisasi GPU pada level sekuens. Self-attention membuka paralelisasi penuh selama training, memungkinkan pemrosesan korpus berskala terabyte.
* **Mitigasi OOV pada Domain Spesifik**: Dalam industri perbankan, hukum, dan medis, istilah teknis (misal: `"trombositopenia"`, `"kebijakan countercyclical"`) sering gagal diproses oleh tokenizer berbasis kata utuh (*whole-word*). Subword tokenization memecah kata langka menjadi unit sub-morfemik yang tetap memiliki makna representasional tanpa menghasilkan token `<UNK>`.
* **Pengendalian Efisiensi Infrastruktur LLM**: Kompleksitas komputasi dan konsumsi VRAM dari attention standar berskala kuadratik $O(N^2)$ terhadap panjang konteks ($N$). Tanpa pemahaman mendalam tentang manipulasi matriks $Q, K, V$, insinyur AI tidak dapat mengoptimalkan ukuran batch, context window, atau mendiagnosis *CUDA Out-of-Memory* (OOM) pada beban kerja produksi.

---

### 4. Arsitektur & Diagram Komponen

Berikut adalah arsitektur komputasi tingkat tinggi dari blok Transformer (pendekatan *Pre-Layer Normalization*):

```
Input Sequence: [x_1, x_2, ..., x_N]
         │
         ▼
┌────────────────────────────────────────────────────────┐
│             Token & Positional Embedding               │
│       Input Vectors: X = Token_Emb + Pos_Emb           │
└──────────────────────────┬─────────────────────────────┘
                           │
         ┌─────────────────┴─────────────────┐
         │ (Residual Connection 1)           │
         │                                   ▼
         │                        ┌────────────────────┐
         │                        │  LayerNorm (RMS)   │
         │                        └──────────┬─────────┘
         │                                   │
         │                                   ▼
         │                        ┌────────────────────┐
         │                        │  Multi-Head        │
         │                        │  Self-Attention    │
         │                        │  (Q, K, V Proj)    │
         │                        └──────────┬─────────┘
         │                                   │
         ▼                                   ▼
       [ + ] <───────────────────────────────┘
         │
         │ (Residual Connection 2)
         ├───────────────────────────────────┐
         │                                   ▼
         │                        ┌────────────────────┐
         │                        │  LayerNorm (RMS)   │
         │                        └──────────┬─────────┘
         │                                   │
         │                                   ▼
         │                        ┌────────────────────┐
         │                        │ Feed-Forward Net   │
         │                        │ (MLP: Linear->GELU │
         │                        │  ->Linear)         │
         │                        └──────────┬─────────┘
         │                                   │
         ▼                                   ▼
       [ + ] <───────────────────────────────┘
         │
         ▼
Output Representations: Z ∈ ℝ^(B × N × d_model)
```

#### Diagram Alir Komputasi Scaled Dot-Product Attention:

```
  Queries (Q)          Keys (K)
       │                  │
       │                  ▼
       │               Transpose(K)
       │                  │
       └────────┬─────────┘
                ▼
        MatMul (Q × K^T)  --> Dimensi: (Batch, Heads, N, N)
                │
                ▼
        Scale (÷ √d_k)   --> Stabilisasi variansi gradien
                │
                ▼
        Mask (Opsional)  --> Masking Kausal / Padding (Add -1e9)
                │
                ▼
             Softmax     --> Menghasilkan Matriks Attention Weights (A)
                │
                ├─────────┐
                ▼         ▼
             Dropout   Values (V)
                │         │
                └────┬────┘
                     ▼
             MatMul (A × V) --> Dimensi: (Batch, Heads, N, d_v)
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Byte-Pair Encoding (BPE)
BPE adalah algoritma kompresi data adaptif yang dimodifikasi untuk segmentasi token. Dimulai dari alfabet karakter dasar ditambah penanda akhir kata, algoritma secara iteratif menghitung pasangan simbol (*bigram*) yang paling sering muncul (*highest frequency*) dalam korpus dan menggabungkannya (*merge*) menjadi simbol baru.

$$P_{(u, v)} = \text{Count}(u, v) \quad \forall \, u, v \in \mathcal{V}$$

Proses ini diulang hingga ukuran kosakata target $|\mathcal{V}|$ tercapai. Pada tahap inferensi, teks baru disegmentasi berdasarkan aturan *merges* yang telah diurutkan berdasarkan prioritas frekuensi training.

#### 5.2 Sinusoidal Positional Encoding
Karena operasi self-attention bersifat invarian terhadap permutasi urutan token ($\text{Attention}(P X) = P \text{Attention}(X)$ untuk matriks permutasi $P$), model memerlukan sinyal eksplisit mengenai posisi absolut/relatif token. Vaswani et al. (2017) merumuskan fungsi periodik sinusoidal deterministik:

$$PE_{(pos, 2i)} = \sin\left(\frac{pos}{10000^{\frac{2i}{d_{model}}}}\right)$$

$$PE_{(pos, 2i+1)} = \cos\left(\frac{pos}{10000^{\frac{2i}{d_{model}}}}\right)$$

Di mana $pos$ adalah indeks posisi token dalam sekuens, dan $i \in [0, \dots, \frac{d_{model}}{2} - 1]$ adalah indeks dimensi embedding. Skema ini memungkinkan model mempelajari relasi posisi relatif secara linier karena untuk setiap offset tetap $k$, terdapat transformasi linier sedemikian rupa sehingga $PE_{pos+k}$ dapat diproyeksikan dari $PE_{pos}$.

#### 5.3 Scaled Dot-Product Attention
Diberikan input representasi $X \in \mathbb{R}^{N \times d_{model}}$, matriks *Query* ($Q$), *Key* ($K$), dan *Value* ($V$) dihitung melalui proyeksi linear:

$$Q = X W_Q, \quad K = X W_K, \quad V = X W_V$$

Di mana $W_Q, W_K \in \mathbb{R}^{d_{model} \times d_k}$ dan $W_V \in \mathbb{R}^{d_{model} \times d_v}$. Komputasi *Scaled Dot-Product Attention* diformulasikan sebagai:

$$\text{Attention}(Q, K, V) = \text{softmax}\left(\frac{Q K^T}{\sqrt{d_k}} + M\right) V$$

* **Faktor Skala $\frac{1}{\sqrt{d_k}}$**: Jika elemen-elemen dari $q$ dan $k$ adalah variabel acak independen dengan rata-rata 0 dan variansi 1, maka hasil kali titik $q \cdot k = \sum_{j=1}^{d_k} q_j k_j$ memiliki rata-rata 0 dan variansi $d_k$. Untuk $d_k$ yang besar, nilai skalar hasil perkalian membengkak, mendorong fungsi softmax ke daerah saturasi dengan gradien yang sangat kecil (*vanishing gradient*). Pembagian dengan $\sqrt{d_k}$ menormalkan kembali variansi menjadi 1.
* **Masking Matrix ($M$)**: Untuk masking kausal (pada autoregressive decoder), elemen $M_{i, j} = -\infty$ untuk $j > i$, dan $0$ untuk $j \le i$. Hal ini mencegah token pada posisi $i$ memperhatikan token masa depan ($j > i$).

#### 5.4 Multi-Head Attention (MHA)
Alih-alih menghitung satu distribusi perhatian tunggal dengan dimensi $d_{model}$, MHA memproyeksikan representasi ke dalam $h$ sub-ruang representasi yang berbeda secara paralel:

$$\text{MHA}(Q, K, V) = \text{Concat}(\text{head}_1, \dots, \text{head}_h) W^O$$

$$\text{head}_i = \text{Attention}(Q W_i^Q, K W_i^K, V W_i^V)$$

Di mana $W_i^Q \in \mathbb{R}^{d_{model} \times d_k}$, $W_i^K \in \mathbb{R}^{d_{model} \times d_k}$, $W_i^V \in \mathbb{R}^{d_{model} \times d_v}$, dan $W^O \in \mathbb{R}^{h d_v \times d_{model}}$. Secara konvensional, $d_k = d_v = d_{model} / h$. Hal ini memungkinkan model secara simultan menangkap informasi sintaktis, semantik, dan koreferensi dari sub-ruang representasi yang berbeda tanpa menambah biaya komputasi total secara signifikan.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi modular arsitektur Transformer dasar menggunakan PyTorch 2.x dengan *type annotations*, penanganan validasi bentuk tensor, masking, dan arsitektur *Pre-LN Transformer Block*.

```python
import math
from typing import Optional, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F


class SinusoidalPositionalEncoding(nn.Module):
    """
    Menghasilkan Sinusoidal Positional Encoding absolut deterministik.
    Formula:
        PE(pos, 2i)   = sin(pos / 10000^(2i / d_model))
        PE(pos, 2i+1) = cos(pos / 10000^(2i / d_model))
    """

    def __init__(self, d_model: int, max_seq_len: int = 5000) -> None:
        super().__init__()
        if d_model % 2 != 0:
            raise ValueError(f"d_model harus bilangan genap, diterima: {d_model}")

        self.d_model = d_model
        pe = torch.zeros(max_seq_len, d_model, dtype=torch.float32)
        position = torch.arange(0, max_seq_len, dtype=torch.float32).unsqueeze(1)
        
        div_term = torch.exp(
            torch.arange(0, d_model, 2, dtype=torch.float32) * (-math.log(10000.0) / d_model)
        )

        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)

        # Buffer didaftarkan agar ikut tersimpan dalam state_dict tanpa parameter gradient
        self.register_buffer("pe", pe.unsqueeze(0), persistent=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Tensor input dengan shape (Batch_Size, Seq_Len, d_model)
        Returns:
            Tensor hasil penambahan positional encoding dengan shape identik.
        """
        seq_len = x.size(1)
        if seq_len > self.pe.size(1):
            raise ValueError(
                f"Panjang sekuens ({seq_len}) melebihi max_seq_len ({self.pe.size(1)})"
            )
        return x + self.pe[:, :seq_len, :]


class MultiHeadAttention(nn.Module):
    """
    Multi-Head Attention modular dengan scaling factor stabil dan support causal/padding mask.
    """

    def __init__(self, d_model: int, num_heads: int, dropout: float = 0.1) -> None:
        super().__init__()
        if d_model % num_heads != 0:
            raise ValueError(
                f"d_model ({d_model}) harus habis dibagi oleh num_heads ({num_heads})"
            )

        self.d_model = d_model
        self.num_heads = num_heads
        self.d_k = d_model // num_heads

        # Proyeksi linier terpadu untuk efisiensi komputasi matriks Q, K, V
        self.qkv_projection = nn.Linear(d_model, 3 * d_model, bias=False)
        self.out_projection = nn.Linear(d_model, d_model, bias=False)
        self.dropout = nn.Dropout(p=dropout)

        self._reset_parameters()

    def _reset_parameters(self) -> None:
        # Inisialisasi bobot Xavier Glorot seragam untuk kestabilan proyeksi
        nn.init.xavier_uniform_(self.qkv_projection.weight)
        nn.init.xavier_uniform_(self.out_projection.weight)

    def forward(
        self,
        x: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
        is_causal: bool = False,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: Tensor dimensi (Batch_Size, Seq_Len, d_model)
            mask: Optional Boolean/Float Tensor untuk padding masking
                  Shape: (Batch_Size, 1, 1, Seq_Len) atau broadcastable
            is_causal: Jika True, terapkan autoregressive lower-triangular causal mask

        Returns:
            Tuple[Tensor output terproyeksi, Tensor attention weights matrix]
        """
        batch_size, seq_len, _ = x.shape

        # 1. Proyeksikan input ke Q, K, V sekaligus: (B, N, 3 * d_model)
        qkv = self.qkv_projection(x)
        
        # 2. Reshape dan transpose untuk paralelisasi head: (B, num_heads, N, d_k)
        qkv = qkv.reshape(batch_size, seq_len, 3, self.num_heads, self.d_k)
        qkv = qkv.permute(2, 0, 3, 1, 4)
        q, k, v = qkv[0], qkv[1], qkv[2]

        # 3. Scaled Dot-Product Attention: (B, H, N, d_k) x (B, H, d_k, N) -> (B, H, N, N)
        scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.d_k)

        # 4. Penanganan Masking
        if is_causal:
            causal_mask = torch.triu(
                torch.full((seq_len, seq_len), float("-inf"), device=x.device),
                diagonal=1,
            )
            scores = scores + causal_mask.unsqueeze(0).unsqueeze(0)

        if mask is not None:
            # Mask bernilai 0/False diisi nilai floating point minus tak hingga (-1e9)
            if mask.dtype == torch.bool:
                scores = scores.masked_fill(~mask, -1e9)
            else:
                scores = scores + mask

        # 5. Normalisasi probabilitas dan dropout
        attention_weights = F.softmax(scores, dim=-1)
        # Proteksi terhadap NaNs jika ada baris yang termask sepenuhnya
        attention_weights = torch.nan_to_num(attention_weights, nan=0.0)
        attn_applied = self.dropout(attention_weights)

        # 6. Kontraksi bobot dengan Value: (B, H, N, N) x (B, H, N, d_k) -> (B, H, N, d_k)
        context = torch.matmul(attn_applied, v)

        # 7. Rekonstruksi multi-head kembali ke bentuk asal: (B, N, d_model)
        context = context.permute(0, 2, 1, 3).contiguous().reshape(batch_size, seq_len, self.d_model)
        output = self.out_projection(context)

        return output, attention_weights


class FeedForwardNetwork(nn.Module):
    """Position-wise Feed-Forward Network dengan aktivasi GELU dan proyeksi ekspansi."""

    def __init__(self, d_model: int, d_ff: int, dropout: float = 0.1) -> None:
        super().__init__()
        self.w_1 = nn.Linear(d_model, d_ff)
        self.w_2 = nn.Linear(d_ff, d_model)
        self.dropout = nn.Dropout(dropout)
        self.activation = nn.GELU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.w_2(self.dropout(self.activation(self.w_1(x))))


class TransformerBlock(nn.Module):
    """
    Standar Industri Transformer Block dengan konfigurasi Pre-Layer Normalization (Pre-LN).
    Pre-LN menjamin stabilitas propagasi gradien tanpa requiring warm-up yang ekstrem.
    """

    def __init__(
        self,
        d_model: int,
        num_heads: int,
        d_ff: int,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.ln_1 = nn.LayerNorm(d_model, eps=1e-5)
        self.mha = MultiHeadAttention(d_model=d_model, num_heads=num_heads, dropout=dropout)
        self.dropout_1 = nn.Dropout(dropout)

        self.ln_2 = nn.LayerNorm(d_model, eps=1e-5)
        self.ffn = FeedForwardNetwork(d_model=d_model, d_ff=d_ff, dropout=dropout)
        self.dropout_2 = nn.Dropout(dropout)

    def forward(
        self,
        x: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
        is_causal: bool = False,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        # Sub-layer 1: Pre-LN Multi-Head Attention dengan residual connection
        norm_x = self.ln_1(x)
        attn_out, weights = self.mha(norm_x, mask=mask, is_causal=is_causal)
        x = x + self.dropout_1(attn_out)

        # Sub-layer 2: Pre-LN Feed-Forward Network dengan residual connection
        x = x + self.dropout_2(self.ffn(self.ln_2(x)))

        return x, weights
```

---

### 7. Edge Cases & Failure Modes

Pada lingkungan produksi, kegagalan sistem representasi NLP dan attention umumnya berakar pada masalah numerik dan manipulasi tensor tingkat rendah:

1. **Underflow Akibat Variansi Dot-Product Tidak Ternormalisasi**:
   * *Gejala*: Gradien bernilai nol (*vanishing gradient*) pada lapisan awal attention.
   * *Akar Masalah*: Jika skalar pembagi $\sqrt{d_k}$ dihilangkan, nilai $Q K^T$ meluas proporsional terhadap dimensi head. Distribusi Softmax menjadi menyerupai fungsi *one-hot argmax*, membunuh gradien derivatif: $\frac{\partial S_i}{\partial z_j} = S_i (\delta_{ij} - S_j) \approx 0$.
   * *Solusi*: Terapkan strict scale factor division secara eksplisit sebelum penambahan bias mask atau pemanggilan fungsi softmax.

2. **Causal Leakage pada Autoregressive Inference**:
   * *Gejala*: Model generatif menunjukkan *perplexity* luar biasa rendah saat evaluasi offline, tetapi menghasilkan teks repetitif atau inkoheren total pada saat serving.
   * *Akar Masalah*: Implementasi causal mask tidak menutupi indeks $j > i$ secara ketat, menyebabkan token pada posisi $i$ mendapatkan bocoran representasi fitur dari token masa depan melalui matriks attention.
   * *Solusi*: Gunakan strictly enforced triangular upper mask (`torch.triu(..., diagonal=1)`) bernilai $-\infty$. Lakukan unit-testing terisolasi yang memverifikasi bahwa $\nabla_{x_{t+k}} x_t \equiv 0$ untuk setiap $k > 0$.

3. **Subword Fragmentation & Unicode Inconsistency**:
   * *Gejala*: Tokenizer menghasilkan fragmen byte yang terpecah-pecah secara masif pada karakter beraksen, simbol mata uang, atau emoji, menghabiskan alokasi context window.
   * *Akar Masalah*: Inkonsistensi normalisasi Unicode (NFC vs. NFD) sebelum tokenisasi subword. Karakter seperti `é` dapat direpresentasikan sebagai satu code point (`U+00E9`) atau gabungan dua code point (`U+0065` + `U+0301`).
   * *Solusi*: Standarisasi pipeline *pre-tokenization* menggunakan Unicode Normalization Form C (NFC) sebelum teks dimasukkan ke modul BPE.

4. **Karakteristik OOM Eksponensial Terhadap Panjang Sekuens**:
   * *Gejala*: Kegagalan komputasi CUDA saat menangani sekuens panjang (misal: $N > 4096$).
   * *Akar Masalah*: Memori matriks attention berukuran $O(B \times H \times N^2)$. Penggandaan panjang dokumen dari $2048$ ke $4096$ token melipatgandakan alokasi memori intermediate attention map sebesar 400%.
   * *Solusi*: Terapkan *FlashAttention* (menggunakan *tiling* SRAM GPU dan recomputation) atau beralih ke arsitektur perhatian sparse/linear jika $N \ge 8192$.

---

### 8. Trade-offs & Alternatif Solusi

Setiap keputusan desain dalam fondasi NLP modern melibatkan kompromi fundamental antara latensi komputasi, kapasitas representasi, dan konsumsi memori.

#### Komparasi Varian Mekanisme Attention

| Arsitektur Attention | Kompleksitas Waktu | Kompleksitas Memori | Throughput Serving | Kualitas Representasi | Skenario Penggunaan Utama |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Multi-Head Attention (MHA)** | $O(N^2 \cdot d)$ | $O(B \cdot H \cdot N^2 + B \cdot N \cdot d)$ | Baseline | Maksimal (State-of-the-Art) | Training dasar, context window standar ($N \le 4096$) |
| **Multi-Query Attention (MQA)** | $O(N^2 \cdot d)$ | $O(B \cdot 1 \cdot N^2 + B \cdot N \cdot d_k)$ | Sangat Tinggi ($10\times$ KV reduction) | Penurunan minor pada tugas penalaran kompleks | High-throughput real-time decoding serving |
| **Grouped-Query Attention (GQA)** | $O(N^2 \cdot d)$ | $O(B \cdot G \cdot N^2 + B \cdot N \cdot G \cdot d_k)$ | Tinggi (Optimal trade-off) | Nyaris setara penuh dengan MHA | Arsitektur modern (LLaMA 2/3, Mistral) |
| **FlashAttention-2** | $O(N^2 \cdot d)$ | $O(B \cdot N \cdot d)$ (IO-Aware SRAM Tiling) | $2-4\times$ lebih cepat dari vanilla MHA | Identik matematis dengan MHA | Standar de-facto eksekusi GPU skala enterprise |

#### Komparasi Skema Positional Representation

| Metode Posisi | Generalisasi Panjang Sekuens (> Max Length) | Overhead Komputasi | Relasi Posisi | Catatan Implementasi |
| :--- | :--- | :--- | :--- | :--- |
| **Sinusoidal Absolute** | Buruk (degradasi tajam di luar panjang context training) | Sangat Rendah (dihitung sekali / static lookup) | Absolut | Transformer asli (Vaswani et al.) |
| **Learned Absolute** | Nol (tidak dapat mengekstrapolasi posisi baru) | Sangat Rendah (memerlukan alokasi embedding table) | Absolut | BERT, GPT-2 |
| **Rotary Position Embedding (RoPE)** | Moderat hingga Sangat Baik (bisa diskalakan via NTK-aware scaling) | Rendah (operasi rotasi kompleks per head vektor $Q$ dan $K$) | Relatif | Fondasi LLM kontemporer (LLaMA, PaLM) |
| **ALiBi (Attention with Linear Biases)** | Luar Biasa (bisa ekstrapolasi sekuens yang jauh lebih panjang) | Nol parameter tambahan (bias skalar pada logit attention) | Relatif | MPT, BLOOM |

---

### 9. Best Practices & Standar Industri

1. **Adopsi Arsitektur Pre-Layer Normalization (Pre-LN)**:
   * *Prinsip*: Letakkan Layer Normalization pada *residual branch* sebelum modul Self-Attention dan FFN, bukan setelah penambahan residual (Post-LN).
   * *Justifikasi*: Pre-LN menjaga gradien tetap mengalir langsung melalui *residual stream* utama dari lapisan akhir ke lapisan awal, mengeliminasi kebutuhan *warm-up learning rate* yang rapuh secara numerik.
2. **Penggunaan Aktivasi GELU / SwiGLU**:
   * *Prinsip*: Gantikan aktivasi ReLU standar pada lapisan Feed-Forward Network dengan Gaussian Error Linear Units (GELU) atau variasinya (SwiGLU).
   * *Justifikasi*: Mencegah masalah *dead neurons* dengan memberikan gradien non-nol pada nilai input negatif kecil, menghasilkan konvergensi model yang lebih halus dan representasi yang lebih kaya.
3. **Standarisasi Tipe Presisi Floating-Point (BF16 vs FP16)**:
   * *Prinsip*: Gunakan `torch.bfloat16` dibandingkan `torch.float16` untuk komputasi attention pada GPU arsitektur Ampere ke atas (A100, H100, RTX 3090+).
   * *Justifikasi*: Bfloat16 mempertahankan dynamic range yang identik dengan FP32 (8 bit exponent), mencegah underflow numerik saat menghitung matriks $Q K^T$ sebelum softmax tanpa membutuhkan *dynamic loss scaling* yang kompleks.
4. **Verifikasi Matriks Isolasi Causal dan Padding**:
   * *Prinsip*: Jangan pernah menggabungkan perhitungan loss pada token padding.
   * *Justifikasi*: Cross-entropy loss harus mengabaikan token padding via parameter `ignore_index=-100` agar backpropagation tidak terdistorsi oleh pola token sintaksis kosong.

---

### 10. Hands-on Lab Exercise

#### Skenario Enterprise
Anda adalah seorang Lead AI Platform Engineer pada institusi keuangan. Divisi *compliance* membutuhkan model pendeteksi anomali pada klausul kontrak pinjaman. Dokumen kontrak memiliki panjang bervariasi dengan pola sintaksis kompleks. Tugas Anda adalah mengimplementasikan modul attention layer kustom, memverifikasi integritas masking kausal dan padding, serta mengukur footprint memori terhadap variasi panjang sekuens.

#### Langkah-langkah Implementasi

```python
import time
import torch
import torch.nn as nn

# Pastikan script berjalan pada GPU jika tersedia
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Menggunakan compute engine: {device}")

# ==========================================
# Langkah 1: Inisialisasi Transformer Block
# ==========================================
d_model = 256
num_heads = 8
d_ff = 1024
max_seq_len = 512
batch_size = 2

transformer_block = TransformerBlock(
    d_model=d_model,
    num_heads=num_heads,
    d_ff=d_ff,
    dropout=0.1
).to(device)
transformer_block.eval()

# ==========================================
# Langkah 2: Simulasi Input dengan Padding Mask
# ==========================================
# Dokumen 1 memiliki 5 token aktual, Dokumen 2 memiliki 3 token aktual (2 token padding)
seq_len = 5
input_embeddings = torch.randn(batch_size, seq_len, d_model, device=device)

# Mask: True menunjukkan token valid, False menunjukkan token padding
padding_mask = torch.tensor([
    [True, True, True, True, True],
    [True, True, True, False, False]
], dtype=torch.bool, device=device).unsqueeze(1).unsqueeze(2)  # Shape: (B, 1, 1, N)

# Eksekusi blok Transformer dengan Padding Mask
with torch.no_grad():
    output_padded, attn_weights_padded = transformer_block(
        input_embeddings, 
        mask=padding_mask, 
        is_causal=False
    )

print("\n--- Verifikasi Padding Mask ---")
print("Attention Weights Batch 2 (Token Padding harus memiliki bobot perhatian ~0):")
print(attn_weights_padded[1, 0, :, :]) # Menampilkan Head 0 Dokumen 2

# Verifikasi: Kolom 3 dan 4 (posisi padding) harus bernilai nol
assert torch.all(attn_weights_padded[1, 0, :, 3:] == 0.0), "Kegagalan: Padding leakage terdeteksi!"
print("Verifikasi Padding: Lolos (Zero-leakage confirmed).")

# ==========================================
# Langkah 3: Verifikasi Integritas Causal Mask
# ==========================================
with torch.no_grad():
    output_causal, attn_weights_causal = transformer_block(
        input_embeddings, 
        is_causal=True
    )

print("\n--- Verifikasi Causal Mask ---")
print("Attention Weights Matrix Batch 1 (Harus berbentuk Lower Triangular):")
print(attn_weights_causal[0, 0, :, :])

# Verifikasi segitiga atas (upper triangle di luar diagonal) bernilai nol
upper_triangle = torch.triu(attn_weights_causal[0, 0, :, :], diagonal=1)
assert torch.all(upper_triangle == 0.0), "Kegagalan: Causal future-token leakage terdeteksi!"
print("Verifikasi Kausalitas: Lolos (Strict autoregressive constraint terpenuhi).")

# ==========================================
# Langkah 4: Benchmark Skalabilitas Kompleksitas Komputasi O(N^2)
# ==========================================
print("\n--- Benchmark Latensi Scaling Context Window ---")
sequence_lengths = [128, 256, 512, 1024, 2048]
bench_mha = MultiHeadAttention(d_model=512, num_heads=8).to(device)
bench_mha.eval()

for n in sequence_lengths:
    x_bench = torch.randn(1, n, 512, device=device)
    
    # Warm-up GPU
    with torch.no_grad():
        for _ in range(5):
            _ = bench_mha(x_bench)
            
    if device.type == "cuda":
        torch.cuda.synchronize()
        
    start_time = time.perf_counter()
    iterations = 20
    with torch.no_grad():
        for _ in range(iterations):
            _ = bench_mha(x_bench)
            
    if device.type == "cuda":
        torch.cuda.synchronize()
        
    avg_latency = (time.perf_counter() - start_time) / iterations * 1000
    print(f"Sequence Length: {n:4d} | Execution Time Rata-rata: {avg_latency:6.2f} ms")
```

#### Panduan Troubleshooting & Evaluasi Lab
1. **Error: Dimension Mismatch pada Matriks Perjumlahan Residual**:
   * *Penyebab*: Dimensi proyeksi linear pada FeedForwardNetwork atau Attention out-projection tidak menghasilkan dimensi akhir yang sama dengan `d_model`.
   * *Solusi*: Pastikan `out_projection.weight` selalu memetakan dari `d_model` ke `d_model`.
2. **Peringatan NaNs pada Attention Weights**:
   * *Penyebab*: Terdapat baris di mana seluruh token di-mask (misal: urutan token yang sepenuhnya padding). Akibatnya, nilai softmax menjadi $\frac{e^{-\infty}}{\sum e^{-\infty}} = \frac{0}{0} = \text{NaN}$.
   * *Solusi*: Terapkan sanitasi `torch.nan_to_num(attention_weights, nan=0.0)` secara ketat segera setelah operasi softmax seperti pada implementasi di Bab 6.